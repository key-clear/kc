odoo.define('website_sign.PDFIframe', function(require) {
    'use strict';

    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var Widget = require('web.Widget');

    var _t = core._t;

    var PDFIframe = Widget.extend({
        init: function(parent, attachmentLocation, editMode, datas, role) {
            this._super(parent);

            this.attachmentLocation = attachmentLocation;
            this.editMode = editMode;
            for(var dataName in datas) {
                this._set_data(dataName, datas[dataName]);
            }
            
            this.role = role || 0;
            this.configuration = {};

            this.fullyLoaded = new $.Deferred();
        },

        _set_data: function(dataName, data) {
            this[dataName] = {};
            if(data instanceof jQuery) {
                var self = this;
                data.each(function(i, el) {
                    self[dataName][$(el).data('id')] = $(el).data();
                }).detach();
            } else {
                for(var i = 0 ; i < data.length ; i++) {
                    this[dataName][data[i].id] = data[i];
                }
            }
        },

        start: function() {
            this.$iframe = this.$el; // this.$el will be changed to the iframe html tag once loaded

            this.pdfView = (this.$iframe.attr('readonly') === "readonly");
            this.readonlyFields = this.pdfView || this.editMode;
            
            var viewerURL = "/website/static/lib/pdfjs/web/viewer.html?file=";
            viewerURL += encodeURIComponent(this.attachmentLocation).replace(/'/g,"%27").replace(/"/g,"%22") + "#page=1&zoom=page-width";
            this.$iframe.attr('src', viewerURL);
            
            this.waitForPDF();
            return $.when(this._super(), this.fullyLoaded);
        },

        waitForPDF: function() {
            if(this.$iframe.contents().find('#errorMessage').is(":visible")) {
                this.fullyLoaded.resolve();
                return Dialog.alert(this, _t("Need a valid PDF to add signature fields !"));
            }

            var nbPages = this.$iframe.contents().find('.page').length;
            var nbLayers = this.$iframe.contents().find('.textLayer').length;
            if(nbPages > 0 && nbLayers > 0) {
                this.nbPages = nbPages;
                this.doPDFPostLoad();
            } else {
                var self = this;
                setTimeout(function() { self.waitForPDF(); }, 50);
            }
        },

        doPDFPostLoad: function() {
            var self = this;
            this.setElement(this.$iframe.contents().find('html'));

            this.$('#openFile, #pageRotateCw, #pageRotateCcw, #pageRotateCcw').add(this.$('#lastPage').next()).hide();
            this.$('button#print').prop('title', _t("Print original document"));
            this.$('button#download').prop('title', _t("Download original document"));
            this.$('button#zoomOut').click().click();
            
            for(var i = 1 ; i <= this.nbPages ; i++) {
                this.configuration[i] = [];
            }

            var $cssLink = $("<link/>", {
                rel: "stylesheet", type: "text/css",
                href: "/website_sign/static/src/css/iframe.css"
            });
            var $faLink = $("<link/>", {
                rel: "stylesheet", type: "text/css",
                href: "/web/static/lib/fontawesome/css/font-awesome.css"
            });
            var $jqueryLink = $("<link/>", {
                rel: "stylesheet", type: "text/css",
                href: "/web/static/lib/jquery.ui/jquery-ui.css"
            });
            var $jqueryScript = $("<script></script>", {
                type: "text/javascript",
                src: "/web/static/lib/jquery.ui/jquery-ui.js"
            });
            this.$('head').append($cssLink, $faLink, $jqueryLink, $jqueryScript);

            var waitFor = [];

            $(Object.keys(this.signatureItems).map(function(id) { return self.signatureItems[id]; }))
                .sort(function(a, b) {
                    if(a.page !== b.page) {
                        return (a.page - b.page);
                    }

                    if(Math.abs(a.posY - b.posY) > 0.01) {
                        return (a.posY - b.posY);
                    } else {
                        return (a.posX - b.posX);
                    }
                }).each(function(i, el) {
                    var $signatureItem = self.createSignatureItem(
                        self.types[parseInt(el.type || el.type_id[0])],
                        !!el.required,
                        parseInt(el.responsible || el.responsible_id[0]) || 0,
                        parseFloat(el.posX),
                        parseFloat(el.posY),
                        parseFloat(el.width),
                        parseFloat(el.height),
                        el.value
                    );
                    $signatureItem.data({itemId: el.id, order: i});

                    self.configuration[parseInt(el.page)].push($signatureItem);
                }); 

            $.when.apply($, waitFor).then(function() {
                refresh_interval();

                self.$('.o_sign_signature_item').each(function(i, el) {
                    self.updateSignatureItem($(el));
                });
                self.updateFontSize();

                self.$('#viewerContainer').css('visibility', 'visible').animate({'opacity': 1}, 1000);
                self.fullyLoaded.resolve();

                /**
                 * This function is called every 2sec to check if the PDFJS viewer did not detach some signature items.
                 * Indeed, when scrolling, zooming, ... the PDFJS viewer replaces page content with loading icon, removing
                 * any custom content with it.
                 * Previous solutions were tried (refresh after scroll, on zoom click, ...) but this did not always work
                 * for some reason when the PDF was too big.
                 */
                function refresh_interval() {
                    try { // if an error occurs it means the iframe has been detach and will be reinitialized anyway (so the interval must stop)
                        self.refreshSignatureItems();
                        self.refresh_timer = setTimeout(refresh_interval, 2000);
                    } catch (e) {}
                }
            });
        },

        refreshSignatureItems: function() {
            for(var page in this.configuration) {
                var $pageContainer = this.$('body #pageContainer' + page);
                for(var i = 0 ; i < this.configuration[page].length ; i++) {
                    if(!this.configuration[page][i].parent().hasClass('page')) {
                        $pageContainer.append(this.configuration[page][i]);
                    }
                }
            }
            this.updateFontSize();
        },

        updateFontSize: function() {
            var self = this;
            var normalSize = this.$('.page').first().innerHeight() * 0.015;
            this.$('.o_sign_signature_item').each(function(i, el) {
                var $elem = $(el);
                var size = parseFloat($elem.css('height'));
                if($.inArray(self.types[$elem.data('type')].type, ['signature', 'initial', 'textarea']) > -1) {
                    size = normalSize;
                }

                $elem.css('font-size', size * 0.8);
            });
        },

        createSignatureItem: function(type, required, responsible, posX, posY, width, height, value) {
            var self = this;
            var readonly = this.readonlyFields || (responsible > 0 && responsible !== this.role) || !!value;

            var $signatureItem = $(core.qweb.render('website_sign.signature_item', {
                editMode: this.editMode,
                readonly: readonly,
                type: type['type'],
                value: (value)? ("" + value).split('\n').join('<br/>') : "",
                placeholder: type['placeholder']
            }));

            return $signatureItem.data({type: type['id'], required: required, responsible: responsible, posx: posX, posy: posY, width: width, height: height})
                                 .data('hasValue', !!value);
        },

        deleteSignatureItem: function($item) {
            var pageNo = parseInt($item.parent().prop('id').substr('pageContainer'.length));
            $item.remove();
            for(var i = 0 ; i < this.configuration[pageNo].length ; i++) {
                if(this.configuration[pageNo][i].data('posx') === $item.data('posx') && this.configuration[pageNo][i].data('posy') === $item.data('posy')) {
                    this.configuration[pageNo].splice(i, 1);
                }
            }
        },

        updateSignatureItem: function($signatureItem) {
            var posX = $signatureItem.data('posx'), posY = $signatureItem.data('posy');
            var width = $signatureItem.data('width'), height = $signatureItem.data('height');

            if(posX < 0) {
                posX = 0;
            } else if(posX+width > 1.0) {
                posX = 1.0-width;
            }
            if(posY < 0) {
                posY = 0;
            } else if(posY+height > 1.0) {
                posY = 1.0-height;
            }

            $signatureItem.data({posx: Math.round(posX*1000)/1000, posy: Math.round(posY*1000)/1000})
                          .css({left: posX*100 + '%', top: posY*100 + '%', width: width*100 + '%', height: height*100 + '%'});

            var resp = $signatureItem.data('responsible');
            $signatureItem.toggleClass('o_sign_signature_item_required', ($signatureItem.data('required') && (this.editMode || resp <= 0 || resp === this.role)))
                          .toggleClass('o_sign_signature_item_pdfview', (this.pdfView || !!$signatureItem.data('hasValue') || (resp !== this.role && resp > 0 && !this.editMode)));
        },

        disableItems: function() {
            this.$('.o_sign_signature_item').addClass('o_sign_signature_item_pdfview').removeClass('ui-selected');
        },

        destroy: function() {
            clearTimeout(this.refresh_timer);
            this._super.apply(this, arguments);
        },
    });

    return PDFIframe;
});


odoo.define('website_sign.Document', function(require) {
    'use strict';

    var ajax = require('web.ajax');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var PDFIframe = require('website_sign.PDFIframe');
    var Widget = require('web.Widget');

    var _t = core._t;

    var ChatterDialog = Dialog.extend({
        template: "website_sign.chatter",

        init: function(parent, requestID, token, sendAccess, accessToken, options) {
            options = (options || {});
            options.title = options.title || _t("History");
            options.size = options.size || "medium";

            this.sendAccess = sendAccess;

            if(!options.buttons) {
                options.buttons = [];
                if(this.sendAccess) {
                    options.buttons.push({text: _t("Send note"), classes: "btn-primary", click: function() {
                        var self = this;
                        ajax.jsonRpc('/sign/send_note/' + requestID + '/' + token, 'call', {
                            access_token: accessToken,
                            message: this.$('textarea').val(),
                        }).then(function() {
                            self.do_notify(_t("Success"), _t("Your message has been sent."));
                        }).always(function() {
                            self.close();
                        });
                    }});
                }
                options.buttons.push({text: _t("Cancel"), close: true});
            }

            this._super(parent, options);

            this.requestID = requestID;
            this.token = token;
        },

        willStart: function() {
            var self = this;
            var def = ajax.jsonRpc('/sign/get_notes/' + this.requestID + '/' + this.token, 'call', {})
                          .then(function(messages) { self.messages = messages; });

            return $.when(this._super.apply(this, arguments), def);
        },
    });

    var Document = Widget.extend({
        start: function() {
            this.attachmentLocation = this.$('#o_sign_input_attachment_location').val();
            this.requestID = parseInt(this.$('#o_sign_input_signature_request_id').val());
            this.requestToken = this.$('#o_sign_input_signature_request_token').val();
            this.accessToken = this.$('#o_sign_input_access_token').val();
            this.signerName = this.$('#o_sign_signer_name_input_info').val();
            this.sendAccess = this.$('#o_sign_chatter_send_access').val();
            this.types = this.$('.o_sign_field_type_input_info');
            this.items = this.$('.o_sign_item_input_info');

            this.$validateBanner = this.$('.o_sign_validate_banner').first();

            return $.when(this._super.apply(this, arguments), this.initialize_iframe());
        },

        openChatter: function() {
            (new ChatterDialog(this, this.requestID, this.requestToken, this.sendAccess, this.accessToken)).open();
        },

        initialize_iframe: function() {
            this.$iframe = this.$('iframe.o_sign_pdf_iframe').first();
            if(this.$iframe.length > 0) {
                this.iframeWidget = new PDFIframe(this, 
                                                  this.attachmentLocation,
                                                  !this.requestID,
                                                  {
                                                      types: this.types,
                                                      signatureItems: this.items,
                                                  },
                                                  parseInt(this.$('#o_sign_input_current_role').val()));
                return this.iframeWidget.attachTo(this.$iframe);
            }
            return $.when();
        },
    });

    return Document;
});
