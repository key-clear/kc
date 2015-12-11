odoo.define('website_sign.frontend', function(require) {
    'use strict';

    var ajax = require('web.ajax');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var Widget = require('web.Widget');
    var web_editor = require('web_editor.base');
    var website = require('website.website');
    var Document = require('website_sign.Document');
    var PDFIframe = require('website_sign.PDFIframe');
    
    var _t = core._t;

    var SignatureDialog = Dialog.extend({
        template: 'website_sign.signature_dialog',

        events: {
            'click a.o_sign_mode': function(e) {
                this.$modeButtons.removeClass('btn-primary');
                $(e.target).addClass('btn-primary');
                this.$signatureField.jSignature('reset');

                this.mode = $(e.target).data('mode');

                this.$selectStyleButton.toggle(this.mode === 'auto');
                this.$clearButton.toggle(this.mode === 'draw');
                this.$loadButton.toggle(this.mode === 'load');

                if(this.mode === 'load') {
                    this.$loadButton.click();
                }
                this.$signatureField.jSignature((this.mode === 'draw')? "enable" : "disable");

                this.$fontDialog.hide().css('width', 0);
                this.$signerNameInput.trigger('input');
            },

            'input .o_sign_signer_name': function(e) {
                if(this.mode !== 'auto') {
                    return true;
                }
                this.signerName = this.$signerNameInput.val();
                this.printText(SignatureDialog.fonts[this.currentFont], this.getSignatureText());
            },

            'click .o_sign_select_style': function(e) {
                var self = this;
                this.$fontDialog.find('a').empty().append($('<div/>').addClass("o_sign_loading"));
                this.$fontDialog.show().animate({'width': self.$fontDialog.find('a').first().height() * self.signatureRatio * 1.25}, 500, function() {
                    self.buildPreviewButtons();
                });
            },

            'mouseover .o_sign_font_dialog a': function(e) {
                this.currentFont = $(e.currentTarget).data('font-nb');
                this.$signerNameInput.trigger('input');
            },

            'click .o_sign_font_dialog a, .o_sign_signature': function(e) {
                this.$fontDialog.hide().css('width', 0);
            },

            'click .o_sign_clean': function (e) {
                this.$signatureField.jSignature('reset');
            },

            'change .o_sign_load': function(e) {
                var f = e.target.files[0];
                if(f.type.substr(0, 5) !== "image") {
                    return false;
                }

                var self = this, reader = new FileReader();
                reader.onload = function(e) {
                    self.printImage(this.result);
                };
                reader.readAsDataURL(f);
            },
        },

        init: function(parent, signerName, options) {
            options = (options || {});

            options.title = options.title || _t("Adopt Your Signature");
            options.size = options.size || 'medium';

            if(!options.buttons) {
                options.buttons = [];
                options.buttons.push({text: _t("Adopt and Sign"), classes: "btn-primary", click: function(e) {
                    this.confirmFunction(this.$signerNameInput.val(), this.$signatureField.jSignature("getData"));
                }});
                options.buttons.push({text: _t("Cancel"), close: true});
            }

            this._super(parent, options);

            this.signerName = signerName;

            this.signatureRatio = 3.0;
            this.signatureType = 'signature';
            this.currentFont = 0;
            this.mode = 'auto';

            this.confirmFunction = function() {};
        },

        start: function() {
            this.$modeButtons = this.$('a.o_sign_mode');
            this.$signatureField = this.$(".o_sign_signature").first();
            this.$fontDialog = this.$(".o_sign_font_dialog").first();
            this.$fontSelection = this.$(".o_sign_font_selection").first();
            for(var i = 0 ; i < SignatureDialog.fonts.length ; i++) {
                this.$fontSelection.append($("<a/>").data('fontNb', i).addClass('btn btn-block'));
            }
            this.$clearButton = this.$('.o_sign_clean').first();
            this.$selectStyleButton = this.$('.o_sign_select_style').first();
            this.$loadButton = this.$('.o_sign_load').first();
            this.$signerNameInput = this.$(".o_sign_signer_name").first();

            return this._super.apply(this, arguments);
        },

        open: function() {
            var self = this;
            this.opened(function(e) {
                var width = self.$signatureField.width();
                var height = width / self.signatureRatio;

                self.$signatureField.empty().jSignature({
                    'decor-color': 'transparent',
                    'background-color': '#FFF',
                    'color': '#000',
                    'lineWidth': 2,
                    'width': width,
                    'height': height
                });
                self.emptySignature = self.$signatureField.jSignature("getData");

                self.$modeButtons.filter('.btn-primary').click();
                self.$('.modal-footer .btn-primary').focus();
            });

            return this._super.apply(this, arguments);
        },

        getSignatureText: function() {
            var text = this.$signerNameInput.val().replace(/[^\w-'" ]/g, '');
            if(this.signatureType === 'initial') {
                return (text.split(' ').map(function(w) { return w[0]; }).join('.') + '.');
            }
            return text;
        },

        getSVGText: function(font, text) {
            var canvas = this.$signatureField.find('canvas')[0];
            return ("data:image/svg+xml;base64," + btoa(core.qweb.render('website_sign.svg_text', {
                width: canvas.width,
                height: canvas.height,
                font: font,
                text: text,
                type: this.signatureType,
            })));
        },

        printText: function(font, text) {
            return this.printImage(this.getSVGText(font, text));
        },

        printImage: function(imgSrc) {
            var self = this;

            var image = new Image;
            image.onload = function() {
                var width = 0, height = 0;
                var ratio = image.width/image.height

                self.$signatureField.jSignature('reset');
                var $canvas = self.$signatureField.find('canvas'), context = $canvas[0].getContext("2d");

                if(image.width / $canvas[0].width > image.height / $canvas[0].height) {
                    width = $canvas[0].width;
                    height = width / ratio;
                } else {
                    height = $canvas[0].height;
                    width = height * ratio;
                }

                setTimeout(function() {
                    context.drawImage(image, 0, 0, image.width, image.height, ($canvas[0].width - width)/2, ($canvas[0].height - height)/2, width, height);
                }, 0);
            };
            image.src = imgSrc;
        },

        buildPreviewButtons: function() {
            var self = this;
            this.$fontDialog.find('a').each(function(i, el) {
                var $img = $('<img/>', {src: self.getSVGText(SignatureDialog.fonts[$(el).data('fontNb')], self.getSignatureText())});
                $(el).empty().append($img);
            });
        },

        onConfirm: function(fct) {
            this.confirmFunction = fct;
        },
    });

    var SignatureItemNavigator = Widget.extend({
        className: 'o_sign_signature_item_navigator',

        events: {
            'click': 'onClick'
        },

        init: function(parent, types) {
            this._super(parent);

            this.types = types;
            this.started = false;
            this.isScrolling = false;
        },

        start: function() {
            this.$signatureItemNavLine = $('<div/>').addClass("o_sign_signature_item_navline").insertBefore(this.$el);
            this.setTip(_t('Click to start'));
            this.$el.focus();

            return this._super();
        },

        setTip: function(tip) {
            this.$el.html(tip);
        },

        onClick: function(e) {
            var self = this;

            if(!self.started) {
                self.started = true;

                self.getParent().$iframe.prev().animate({'height': '0px', 'opacity': 0}, {
                    duration: 750,
                    complete: function() {
                        self.getParent().$iframe.prev().hide();
                        self.getParent().refreshSignatureItems();

                        self.onClick();
                    }
                });
                
                return false;
            }

            var $toComplete = self.getParent().checkSignatureItemsCompletion().sort(function(a, b) {
                return ($(a).data('order') || 0) - ($(b).data('order') || 0);
            });
            if($toComplete.length > 0) {
                self.scrollToSignItem($toComplete.first());
            }
        },

        scrollToSignItem: function($item) {
            if(!this.started) {
                return;
            }

            var $container = this.getParent().$('#viewerContainer');
            var $viewer = $container.find('#viewer');
            var containerHeight = $container.outerHeight();
            var viewerHeight = $viewer.outerHeight();

            var scrollOffset = containerHeight/4;
            var scrollTop = $item.offset().top - $viewer.offset().top - scrollOffset;
            if(scrollTop + containerHeight > viewerHeight) {
                scrollOffset += scrollTop + containerHeight - viewerHeight;
            }
            if(scrollTop < 0) {
                scrollOffset += scrollTop;
            }
            scrollOffset += $container.offset().top - this.$el.outerHeight()/2 + parseInt($item.css('height'))/2;

            var duration = Math.min(
                1000, 
                5*(Math.abs($container[0].scrollTop - scrollTop) + Math.abs(parseFloat(this.$el.css('top')) - scrollOffset))
            );

            var self = this;
            this.isScrolling = true;
            var def1 = $.Deferred(), def2 = $.Deferred();
            $container.animate({'scrollTop': scrollTop}, duration, function() {
                def1.resolve();
            });
            this.$el.add(this.$signatureItemNavLine).animate({'top': scrollOffset}, duration, function() {
                def2.resolve();
            });
            $.when(def1, def2).then(function() {
                if($item.val() === "" && !$item.data('signature')) {
                    self.setTip(self.types[$item.data('type')].tip);
                }
                
                self.getParent().refreshSignatureItems();
                $item.focus();
                self.isScrolling = false;
            });

            this.getParent().$('.ui-selected').removeClass('ui-selected');
            $item.addClass('ui-selected').focus();
        },
    });

    var PublicSignerDialog = Dialog.extend({
        template: "website_sign.public_signer_dialog",

        init: function(parent, requestID, requestToken, options) {
            var self = this;
            options = (options || {});

            options.title = options.title || _t("Final Validation");
            options.size = options.size || "medium";

            if(!options.buttons) {
                options.buttons = [];
                options.buttons.push({text: _t("Validate & Send"), classes: "btn-primary", click: function(e) {
                    var name = this.$inputs.eq(0).val();
                    var mail = this.$inputs.eq(1).val();
                    if(!name || !mail || mail.indexOf('@') < 0) {
                        this.$inputs.eq(0).closest('.form-group').toggleClass('has-error', !name);
                        this.$inputs.eq(1).closest('.form-group').toggleClass('has-error', !mail || mail.indexOf('@') < 0);
                        return false;
                    }

                    ajax.jsonRpc("/sign/send_public/" + this.requestID + '/' + this.requestToken, 'call', {
                        name: name,
                        mail: mail,
                    }).then(function() {
                        self.close();
                        self.sent.resolve();
                    });
                }});
                options.buttons.push({text: _t("Cancel"), close: true});
            }

            this._super(parent, options);

            this.requestID = requestID;
            this.requestToken = requestToken;
            this.sent = $.Deferred();
        },

        open: function(name, mail) {
            var self = this;
            this.opened(function() {
                self.$inputs = self.$('input');
                self.$inputs.eq(0).val(name);
                self.$inputs.eq(1).val(mail);
            });
            
            return this._super.apply(this, arguments);
        },
    });

    var ThankYouDialog = Dialog.extend({
        template: "website_sign.thank_you_dialog",

        init: function(parent, options) {
            options = (options || {});
            options.title = options.title || _t("Thank You !") + "<br/>";
            options.subtitle = options.subtitle || _t("Your signature has been saved.");
            options.size = options.size || "medium";

            if(!options.buttons) {
                options.buttons = [];
                options.buttons.push({text: _t("Start Using Odoo Sign Now"), close: true});
            }

            this._super(parent, options);

            this.on('closed', this, function() {
                window.location.href = "https://www.odoo.com/page/sign";
            });
        },
    });

    PDFIframe.include({
        init: function() {
            this._super.apply(this, arguments);

            this.events = _.extend(this.events || {}, {
                'keydown .page .ui-selected': function(e) {
                    if((e.keyCode || e.which) !== 9) {
                        return true;
                    }
                    e.preventDefault(); 
                    this.signatureItemNav.onClick();
                },
            });
        },

        doPDFPostLoad: function() {
            var self = this;
            this.fullyLoaded.then(function() {
                self.signatureItemNav = new SignatureItemNavigator(self, self.types);
                var def = self.signatureItemNav.prependTo(self.$('#viewerContainer'));

                self.checkSignatureItemsCompletion();

                self.$('#viewerContainer').on('scroll', function(e) {
                    if(!self.signatureItemNav.isScrolling && self.signatureItemNav.started) {
                        self.signatureItemNav.setTip('next');
                    }
                });

                return def;
            });

            this._super.apply(this, arguments);
        },

        createSignatureItem: function(type, required, responsible, posX, posY, width, height, value) {
            var self = this;
            var $signatureItem = this._super.apply(this, arguments);
            var readonly = this.readonlyFields || (responsible > 0 && responsible !== this.role) || !!value;

            if(!readonly) {
                if(type['type'] === "signature" || type['type'] === "initial") {
                    $signatureItem.on('click', function(e) {
                        self.refreshSignatureItems();
                        var $signedItems = self.$('.o_sign_signature_item').filter(function(i) {
                            var $item = $(this);
                            return ($item.data('type') === type['id']
                                        && $item.data('signature') && $item.data('signature') !== $signatureItem.data('signature')
                                        && ($item.data('responsible') <= 0 || $item.data('responsible') === $signatureItem.data('responsible')));
                        });
                        
                        if($signedItems.length > 0) {
                            $signatureItem.data('signature', $signedItems.first().data('signature'));
                            $signatureItem.html('<span class="o_sign_helper"/><img src="' + $signatureItem.data('signature') + '"/>');
                            $signatureItem.trigger('input');
                        } else {
                            var signDialog = new SignatureDialog(self, self.getParent().signerName || "");
                            signDialog.signatureType = type['type'];
                            signDialog.signatureRatio = parseFloat($signatureItem.css('width'))/parseFloat($signatureItem.css('height'));

                            signDialog.open().onConfirm(function(name, signature) {
                                if(signature !== signDialog.emptySignature) {
                                    self.getParent().signerName = signDialog.signerName;
                                    $signatureItem.data('signature', signature)
                                                  .empty()
                                                  .append($('<span/>').addClass("o_sign_helper"), $('<img/>', {src: $signatureItem.data('signature')}));
                                } else {
                                    $signatureItem.removeData('signature')
                                                  .empty()
                                                  .append($('<span/>').addClass("o_sign_helper"), type['placeholder']);
                                }

                                $signatureItem.trigger('input').focus();
                                signDialog.close();
                            });
                        }
                    });
                }

                if(type['auto_field']) {
                    $signatureItem.on('focus', function(e) {
                        if($signatureItem.val() === "") {
                            $signatureItem.val(type['auto_field']);
                            $signatureItem.trigger('input');
                        }
                    });
                }

                $signatureItem.on('input', function(e) {
                    self.checkSignatureItemsCompletion(self.role);
                    self.signatureItemNav.setTip('next');
                });
            }

            return $signatureItem;
        },

        checkSignatureItemsCompletion: function() {
            this.refreshSignatureItems();
            var $toComplete = this.$('.o_sign_signature_item.o_sign_signature_item_required:not(.o_sign_signature_item_pdfview)').filter(function(i, el) {
                var $elem = $(el);
                return !(($elem.val() && $elem.val().trim()) || $elem.data('signature'));
            });

            this.signatureItemNav.$el.add(this.signatureItemNav.$signatureItemNavLine).toggle($toComplete.length > 0);
            this.$iframe.trigger(($toComplete.length > 0)? 'pdfToComplete' : 'pdfCompleted');

            return $toComplete;
        },
    });

    Document.include({
        events: {
            'pdfToComplete .o_sign_pdf_iframe': function(e) {
                this.$validateBanner.hide().css('opacity', 0);
            },

            'pdfCompleted .o_sign_pdf_iframe': function(e) {
                this.$validateBanner.show().animate({'opacity': 1}, 500);
            },

            'click .o_sign_view_history': 'openChatter',
            'click .o_sign_validate_banner button': 'signItemDocument',
            'click .o_sign_sign_document_button': 'signDocument',
        },

        custom_events: { // do_notify is not supported in backend so it is simulated with a bootstrap alert inserted in a frontend-only DOM element
            'notification': function(e) {
                $('<div/>', {html: e.data.message}).addClass('alert alert-success').insertAfter(self.$('.o_sign_request_reference_title'));
            },
        },

        start: function() {
            return $.when(this._super.apply(this, arguments), ajax.jsonRpc('/sign/get_fonts', 'call', {}).then(function(data) {
                SignatureDialog.fonts = data;
            }));
        },

        signItemDocument: function(e) {
            var mail = "";
            this.iframeWidget.$('.o_sign_signature_item').each(function(i, el) {
                var value = $(el).val();
                if(value && value.indexOf('@') >= 0) {
                    mail = value;
                }
            });

            if(this.$('#o_sign_is_public_user').length > 0) {
                (new PublicSignerDialog(this, this.requestID, this.requestToken))
                    .open(this.signerName, mail).sent.then(_.bind(_sign, this));
            } else {
                _sign.call(this);
            }

            function _sign() {
                var signatureValues = {};
                for(var page in this.iframeWidget.configuration) {
                    for(var i = 0 ; i < this.iframeWidget.configuration[page].length ; i++) {
                        var $elem = this.iframeWidget.configuration[page][i];
                        var resp = parseInt($elem.data('responsible')) || 0;
                        if(resp > 0 && resp !== this.iframeWidget.role) {
                            continue;
                        }

                        var value = ($elem.val() && $elem.val().trim())? $elem.val() : false;
                        if($elem.data('signature')) {
                            value = $elem.data('signature');
                        }

                        if(!value) {
                            if($elem.data('required')) {
                                this.iframeWidget.checkSignatureItemsCompletion();
                                Dialog.alert(this, _t("Some fields have still to be completed !"), {title: _t("Warning")});
                                return;
                            }
                            continue;
                        }

                        signatureValues[parseInt($elem.data('item-id'))] = value;
                    }
                }

                var self = this;
                ajax.jsonRpc('/sign/sign/' + this.requestID + '/' + this.accessToken, 'call', {
                    signature: signatureValues,
                }).then(function(success) {
                    if(!success) {
                        setTimeout(function() { // To be sure this dialog opens after the thank you dialog below
                            Dialog.alert(self, _t("Sorry, an error occured, please try to fill the document again."), {
                                title: _t("Error"),
                                confirm_callback: function() {
                                    window.location.reload();
                                },
                            });
                        }, 500);
                    }
                });
                this.iframeWidget.disableItems();
                (new ThankYouDialog(this)).open();
            }
        },

        signDocument: function(e) {
            var self = this;

            var signDialog = (new SignatureDialog(this, this.signerName));
            signDialog.open().onConfirm(function(name, signature) {
                var isEmpty = ((signature)? (signDialog.emptySignature === signature) : true);

                signDialog.$('.o_sign_signer_info').toggleClass('has-error', !name);
                signDialog.$('.o_sign_signature_draw').toggleClass('panel-danger', isEmpty).toggleClass('panel-default', !isEmpty);
                if(isEmpty || !name) {
                    return false;
                }

                signDialog.$('.modal-footer .btn-primary').prop('disabled', true);
                signDialog.close();

                if(self.$('#o_sign_is_public_user').length > 0) {
                    (new PublicSignerDialog(self, self.requestID, self.requestToken))
                        .open(name, "").sent.then(_sign);
                } else {
                    _sign();
                }

                function _sign() {
                    ajax.jsonRpc('/sign/sign/' + self.requestID + '/' + self.accessToken, 'call', {
                        signature: ((signature)? signature.substr(signature.indexOf(",")+1) : false)
                    }).then(function(success) {
                        if(!success) {
                            setTimeout(function() { // To be sure this dialog opens after the thank you dialog below
                                Dialog.alert(self, _t("Sorry, an error occured, please try to fill the document again."), {
                                    title: _t("Error"),
                                    confirm_callback: function() {
                                        window.location.reload();
                                    },
                                });
                            }, 500);
                        }
                    });
                    (new ThankYouDialog(self)).open();
                }
            });
        },
    });

    if($('#o_sign_is_website_sign_page').length > 0) {
        ajax.loadXML('/website_sign/static/src/xml/website_sign_common.xml', core.qweb);
        ajax.loadXML('/website_sign/static/src/xml/website_sign_frontend.xml', core.qweb);

        web_editor.ready().then(function() {
            var documentPage = new Document(null);

            return documentPage.attachTo($('body')).then(function() {
                // Geolocation
                var askLocation = ($('#o_sign_ask_location_input').length > 0);
                if(askLocation && navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(function(position) {
                        ajax.jsonRpc('/sign/save_location/' + documentPage.requestID + '/' + documentPage.accessToken, 'call', position.coords);
                    });
                }
            });
        });
    }
});
