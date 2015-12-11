odoo.define('website_sign.dashboard', function(require) {
    'use strict';

    var ControlPanelMixin = require('web.ControlPanelMixin');
    var core = require('web.core');
    var formats = require('web.formats');
    var Model = require('web.Model');
    var Pager = require('web.Pager');
    var session = require('web.session');
    var Widget = require('web.Widget');

    var _t = core._t;
    
    var DashboardRow = Widget.extend({
        template: 'website_sign.dashboard_row',
        events: {
            'click .o_sign_dashboard_item .o_sign_toggle': function(e) {
                var self = this;
                var $toggle = $(e.target), $item = $toggle.closest('.o_sign_dashboard_item');
                session.rpc("/sign/toggle/" + $toggle.data('type') + ((this.tCorrect)? '/template/' : '/document/') + $item.data('id'), {
                    'value': !$item.data($toggle.data('type'))
                }).then(function(value) {
                    $item.data($toggle.data('type'), +value);
                    self.refresh();
                });
                return false;
            },

            'click .o_sign_upload_template_button': function(e) {
                e.preventDefault();
                e.stopImmediatePropagation();
                this.$('.o_sign_upload_template_input').click();
            },

            'change .o_sign_upload_template_input': function(e) {
                var f = e.target.files[0], reader = new FileReader();

                var self = this;
                reader.onload = function(e) {
                    var Template = new Model('signature.request.template');
                    Template.call('upload_from_dashboard', [f.name, e.target.result])
                            .then(function(data) {
                                self.do_action({
                                    type: "ir.actions.client",
                                    tag: 'website_sign.Template',
                                    name: _t("New Template"),
                                    context: {
                                        id: data.template,
                                    },
                                });
                            });
                };
                reader.readAsDataURL(f);
            },

            'click .o_sign_dashboard_item > a': function(e) {
                e.preventDefault();
                var $item = $(e.target).closest('.o_sign_dashboard_item');
                var type = ((this.tCorrect)? "Template" : "Document");
                if(type) {
                    this.do_action({
                        type: "ir.actions.client",
                        tag: 'website_sign.' + type,
                        name: type + " \"" + $item.find('.o_sign_dashboard_item_title').html() + "\"",
                        context: {
                            id: $item.data('id'),
                            token: $item.data('token'),
                            create_uid: $item.data('create_uid'),
                            state: $item.data('state'),
                        },
                    });
                }
            },
        },

        init: function(parent, title, items, tCorrect) {
            this._super(parent);

            this.showArchives = false;
            this.showOnlyFavorites = false;

            this.title = title;
            this.items = items;
            this.tCorrect = tCorrect;
        },

        willStart: function() {
            for(var i = 0 ; i < this.items.length ; i++) {
                this.items[i].title = (this.tCorrect)? this.items[i].attachment_id[1] : this.items[i].reference;
                this.items[i].favorited = (this.items[i].favorited_ids.indexOf(session.uid) >= 0);
                this.items[i].can_archive = (this.tCorrect || this.items[i].state !== 'sent');
                this.items[i].icon = ((this.tCorrect)? "file" : "copy");
                this.items[i].date = ((this.tCorrect)? this.items[i].create_date : ((this.items[i].state !== 'canceled')? this.items[i].last_action_date : false));
            
                if(!this.tCorrect && this.items[i].state !== 'signed') {
                    var items = [];
                    var request_items = this.items[i].request_item_ids;
                    for(var j = 0 ; j < request_items.length ; j++) {
                        items.push({
                            completed: (request_items[j].state === 'completed'),
                            name: (request_items.length > 1)? request_items[j].signer_trigram : request_items[j].partner_id.name,
                        });
                    }

                    this.items[i].signers = {
                        full: request_items.map(function(r) {
                            return r.partner_id.name;
                        }).join(', '),
                        items: items,
                    };
                }
            }

            return this._super();
        },

        start: function() {
            this.$items = this.$('.o_sign_dashboard_item');
            if(this.tCorrect) {
                this.$items = this.$items.not(this.$items.first());
            }

            this.pager = new Pager(this, this.$items.length, 1, 6-this.tCorrect);
            this.pager.on('pager_changed', this, function(state) {
                this.refresh();
            });

            this.$items.each(function(i, el) {
                $(el).data('default_order', i);
            });

            var self = this;
            return this._super.apply(this, arguments).then(function() {
                return self.pager.appendTo(self.$('.o_sign_dashboard_title_nav'));
            });
        },

        refresh: function(showArchives, showOnlyFavorites, sort) {
            var self = this;

            this.showArchives = (showArchives === undefined)? this.showArchives : showArchives;
            this.showOnlyFavorites = (showOnlyFavorites === undefined)? this.showOnlyFavorites : showOnlyFavorites;

            var count = this.$items.filter(function(i, el) {
                return (($(el).data('favorited') || !self.showOnlyFavorites) && (!$(el).data('archived') || self.showArchives));
            }).length;

            this.pager.update_state({size: count});

            if(sort) {
                this.$items = this.$items.sort(function(a, b) {
                    var aFav = $(a).data('favorited'), bFav = $(b).data('favorited');
                    if(aFav !== bFav) {
                        return ((aFav)? -1 : 1);
                    }

                    var aArch = $(a).data('archived'), bArch = $(b).data('archived');
                    if(aArch !== bArch) {
                        return ((aArch)? 1 : -1);
                    }
                    
                    return (parseInt($(a).data('default_order')) - parseInt($(b).data('default_order')));
                });
            }
            this.$('h4').next().append(this.$items.detach());
            this.$el.toggle(!!this.tCorrect);
            
            var nbHidden = 0;
            this.$items.each(function(i) {
                var $item = $(this);

                $item.toggleClass('archived', !!$item.data('archived'));
                if(!self.showArchives && $item.data('archived') || self.showOnlyFavorites && !$item.data('favorited')) {
                    nbHidden++;
                    $item.hide();
                    return;
                }

                self.$el.show();
                $item.toggleClass('o_sign_favorited', !!$item.data('favorited'));
                $item.find('.o_sign_favorite_button').toggleClass('fa-star-o', !$item.data('favorited')).toggleClass('fa-star', !!$item.data('favorited'))
                     .prop('title', (($item.data('favorited'))? _t("Unmark") : _t("Mark")) + _t(" as Favorite"));

                var nb = i - nbHidden + 1;
                $item.toggle(nb >= self.pager.state.current_min && nb < self.pager.state.current_min + self.pager.state.limit);
            });
        },
    });

    var Dashboard = Widget.extend(ControlPanelMixin, {
        className: 'container o_sign_dashboard',

        init: function(parent) {
            var self = this;

            var $toggleGroup = $('<div/>').addClass("o_dropdown");

            var $toggleDropdown = $('<a/>', {'data-toggle': 'dropdown'}).addClass("dropdown-toggle");
            this.$dropdown = $('<ul/>', {'role': 'menu'}).addClass("dropdown-menu o_filters_menu");

            $toggleGroup.append($toggleDropdown);
            $toggleGroup.append(this.$dropdown);

            $toggleDropdown.append($('<span/>').addClass("fa fa-filter"), _t(" Filters "), $('<span/>').addClass("caret"));
            this.$favorite_li = $('<li/>').append($('<a/>', {html: _t("Favorites Only")})).appendTo(this.$dropdown)
                .on('click', function(e) {
                    $(e.currentTarget).toggleClass('selected');
                    self.showOnlyFavorites = $(e.currentTarget).hasClass('selected');
                    self.refresh(true);

                    session.website_sign_favorite = self.showOnlyFavorites;
                });
            this.$dropdown.append($('<li/>').addClass("divider"));
            this.$archive_li = $('<li/>').append($('<a/>', {html: _t("Show Archives")})).appendTo(this.$dropdown)
                .on('click', function(e) {
                    $(e.currentTarget).toggleClass('selected');
                    self.showArchives = $(e.currentTarget).hasClass('selected');
                    self.refresh(true);

                    session.website_sign_archive = self.showArchives;
                });

            this.$favorite_li.toggleClass('selected', !!session.website_sign_favorite);
            this.$archive_li.toggleClass('selected', !!session.website_sign_archive);

            this.cp_content = {$searchview_buttons: $toggleGroup};

            this._super.apply(this, arguments);
        },

        willStart: function() {
            var self = this;

            var Templates = new Model('signature.request.template');
            var SignatureRequests = new Model('signature.request');

            var defTemplates = Templates.query(['attachment_id', 'create_date', 'archived', 'favorited_ids'])
                                        .all()
                                        .then(prepare_templates);

            var defSignatureRequests = SignatureRequests.call('get_dashboard_info')
                                                        .then(prepare_requests);

            return $.when(this._super.apply(this, arguments), defTemplates, defSignatureRequests);

            function prepare_templates(templates) {
                self.templates = templates;
                for(var i = 0 ; i < templates.length ; i++) {
                    templates[i].create_date = formats.format_value(templates[i].create_date, {type: 'datetime'}, '');
                }
            }

            function prepare_requests(requests) {
                self.signature_requests = {
                    sent: [],
                    signed: [],
                    canceled: [],
                };
                for(var i = 0 ; i < requests.length ; i++) {
                    self.signature_requests[requests[i].state].push(requests[i]);
                }
            }
        },

        start: function(parent) {
            var self = this;

            this.showArchives = this.$archive_li.hasClass('selected');
            this.showOnlyFavorites = this.$favorite_li.hasClass('selected');

            this.dashboardRows = [];
            this.dashboardRows.push(new DashboardRow(this, _t("Document Templates"), this.templates, true));
            this.dashboardRows.push(new DashboardRow(this, _t("Signatures in Progress"), this.signature_requests.sent, false));
            this.dashboardRows.push(new DashboardRow(this, _t("Fully Signed"), this.signature_requests.signed, false));
            this.dashboardRows.push(new DashboardRow(this, _t("Canceled"), this.signature_requests.canceled, false));

            var waitFor = [this._super.apply(this, arguments)];
            waitFor.concat(this.dashboardRows.map(function(row) {
                return row.appendTo(self.$el);
            }));

            return $.when.apply($, waitFor).then(function() {
                self.refresh(true);
                self.refresh_cp();
            });
        },

        do_show: function() {
            this._super.apply(this, arguments);
            this.refresh_cp();
        },

        refresh: function(sort) {
            for(var i = 0 ; i < this.dashboardRows.length ; i++) {
                this.dashboardRows[i].refresh(this.showArchives, this.showOnlyFavorites, sort);
            }
        },

        refresh_cp: function() {
            this.update_control_panel({
                breadcrumbs: this.getParent().get_breadcrumbs(),
                cp_content: this.cp_content,
            });
        },
    });

    core.action_registry.add('website_sign.dashboard', Dashboard);
});

odoo.define('website_sign.backend', function(require) {
    'use strict';

    var ajax = require('web.ajax');
    var ControlPanelMixin = require('web.ControlPanelMixin');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var framework = require('web.framework');
    var Model = require('web.Model');
    var session = require('web.session');
    var Widget = require('web.Widget');
    var Document = require('website_sign.Document');
    var PDFIframe = require('website_sign.PDFIframe');
    
    var _t = core._t;

    var SignatureItemCustomDialog = Dialog.extend({
        template: 'website_sign.signature_item_custom_dialog',

        init: function(parent, parties, options) {
            options = options || {};

            options.title = options.title || _t("Customize Field");
            options.size = options.size || "medium";

            if(!options.buttons) {
                options.buttons = [];
                options.buttons.push({text: 'Save', classes: 'btn-primary', close: true, click: function(e) {
                    var resp = parseInt(this.$responsibleSelect.find('select').val());
                    var required = this.$('input[type="checkbox"]').prop('checked');

                    this.getParent().currentRole = resp;
                    this.$currentTarget.data({responsible: resp, required: required}).trigger('itemChange');
                }});
                options.buttons.push({text: 'Remove', classes: 'o_sign_delete_field_button btn-link', close: true, click: function(e) {
                    this.$currentTarget.trigger('itemDelete');
                }});
                options.buttons.push({text: 'Discard', classes: 'btn-default', close: true});
            }

            this._super(parent, options);

            this.parties = parties;
        },

        start: function() {
            this.$responsibleSelect = this.$('.o_sign_responsible_select');

            var self = this;
            return this._super().then(function() {
                setAsResponsibleSelect(self.$responsibleSelect.find('select'), self.$currentTarget.data('responsible'), self.parties);
                self.$('input[type="checkbox"]').prop('checked', self.$currentTarget.data('required'));

                self.set_title(self.title, '<span class="fa fa-long-arrow-right"/> ' + self.$currentTarget.prop('title') + ' Field');
            });
        },

        open: function($signatureItem) {
            this.$currentTarget = $signatureItem;
            this._super.apply(this, arguments);
        },
    });

    var InitialAllPagesDialog = Dialog.extend({
        template: 'website_sign.initial_all_pages_dialog',

        init: function(parent, parties, options) {
            options = options || {};

            options.title = options.title || _t("Add Initials");
            options.size = options.size || "medium";

            if(!options.buttons) {
                options.buttons = [];
                options.buttons.push({text: _t('Add once'), classes: 'btn-primary', close: true, click: function(e) {
                    this.updateTargetResponsible();
                    this.$currentTarget.trigger('itemChange');
                }});
                options.buttons.push({text: _t('Add on all pages'), classes: 'btn-default', close: true, click: function(e) {
                    this.updateTargetResponsible();
                    this.$currentTarget.draggable('destroy').resizable('destroy');
                    this.$currentTarget.trigger('itemClone');
                }});
            }

            this._super(parent, options);

            this.parties = parties;
        },

        start: function() {
            this.$responsibleSelect = this.$('.o_sign_responsible_select_initials');

            var self = this;
            return this._super.apply(this, arguments).then(function() {
                setAsResponsibleSelect(self.$responsibleSelect.find('select'), self.getParent().currentRole, self.parties);
            });
        },

        open: function($signatureItem) {
            this.$currentTarget = $signatureItem;
            this._super.apply(this, arguments);
        },

        updateTargetResponsible: function() {
            var resp = parseInt(this.$responsibleSelect.find('select').val());
            this.getParent().currentRole = resp;
            this.$currentTarget.data('responsible', resp);
        },
    });

    var CreateSignatureRequestDialog = Dialog.extend({
        template: 'website_sign.create_signature_request_dialog',

        init: function(parent, templateID, rolesToChoose, templateName, attachment, options) {
            options = options || {};

            options.title = options.title || _t("Send Signature Request");
            options.size = options.size || "medium";

            options.buttons = (options.buttons || []);
            options.buttons.push({text: _t('Send'), classes: 'btn-primary', click: function(e) {
                this.sendDocument();
            }});
            options.buttons.push({text: _t('Cancel'), classes: 'btn-default', close: true});

            this._super(parent, options);

            this.templateID = templateID;
            this.rolesToChoose = rolesToChoose;
            this.templateName = templateName;
            this.attachment = attachment;
        },

        willStart: function() {
            var ResUsers = new Model('res.users');
            var ResPartners = new Model('res.partner');

            var self = this;
            return $.when(this._super(), ResUsers.query(['partner_id'])
                                                 .filter([['id', '=', session.uid]])
                                                 .first()
                                                 .then(function(user) {
                                                     return ResPartners.query(['name'])
                                                                       .filter([['id', '=', user.partner_id[0]]])
                                                                       .first()
                                                                       .then(prepare_reference);
                                                 })
            );

            function prepare_reference(partner) {
                self.default_reference = "-";
                var split = partner.name.split(' ');
                for(var i = 0 ; i < split.length ; i++) {
                    self.default_reference += split[i][0];
                }
            }
        },

        start: function() {
            this.$subjectInput = this.$('.o_sign_subject_input').first();
            this.$messageInput = this.$('.o_sign_message_textarea').first();
            this.$referenceInput = this.$('.o_sign_reference_input').first();

            this.$subjectInput.val('Signature Request - ' + this.templateName);
            var defaultRef = this.templateName + this.default_reference;
            this.$referenceInput.val(defaultRef).attr('placeholder', defaultRef);

            this.$('.o_sign_warning_message_no_field').first().toggle($.isEmptyObject(this.rolesToChoose));
            this.$('.o_sign_request_signers .o_sign_new_signer').remove();

            setAsPartnerSelect(this.$('.o_sign_request_signers .form-group select')); // Followers
            
            if($.isEmptyObject(this.rolesToChoose)) {
                this.addSigner(0, _t("Signers"), true);
            } else {
                var roleIDs = Object.keys(this.rolesToChoose).sort();
                for(var i = 0 ; i < roleIDs.length ; i++) {
                    var roleID = roleIDs[i];
                    if(roleID !== 0)
                        this.addSigner(roleID, this.rolesToChoose[roleID], false);
                }
            }

            return this._super.apply(this, arguments);
        },

        addSigner: function(roleID, roleName, multiple) {
            var $newSigner = $('<div/>').addClass('o_sign_new_signer form-group');

            $newSigner.append($('<label/>').addClass('col-md-3').html(roleName).data('role', roleID));
            
            var $signerInfo = $('<select/>').attr('placeholder', _t("Write email or search contact..."));
            if(multiple) {
                $signerInfo.attr('multiple', 'multiple');
            }

            var $signerInfoDiv = $('<div/>').addClass('col-md-9');
            $signerInfoDiv.append($signerInfo);

            $newSigner.append($signerInfoDiv);

            setAsPartnerSelect($signerInfo);

            this.$('.o_sign_request_signers').first().prepend($newSigner);
        },

        sendDocument: function() {
            var self = this;

            var completedOk = true;
            self.$('.o_sign_new_signer').each(function(i, el) {
                var $elem = $(el);
                var partnerIDs = $elem.find('select').val();
                if(!partnerIDs || partnerIDs.length <= 0) {
                    completedOk = false;
                    $elem.addClass('has-error');
                    $elem.one('focusin', function(e) {
                        $elem.removeClass('has-error');
                    });
                }
            });
            if(!completedOk) {
                return false;
            }

            var waitFor = [];

            var signers = [];
            self.$('.o_sign_new_signer').each(function(i, el) {
                var $elem = $(el);
                var selectDef = processPartnersSelection($elem.find('select')).then(function(partners) {
                    for(var p = 0 ; p < partners.length ; p++) {
                        signers.push({
                            'partner_id': partners[p],
                            'role': parseInt($elem.find('label').data('role'))
                        });
                    }
                });
                if(selectDef !== false) {
                    waitFor.push(selectDef);
                }
            });

            var followers = [];
            var followerDef = processPartnersSelection(self.$('#o_sign_followers_select')).then(function(partners) {
                followers = partners;
            });
            if(followerDef !== false) {
                waitFor.push(followerDef);
            }

            var subject = self.$subjectInput.val() || self.$subjectInput.attr('placeholder');
            var reference = self.$referenceInput.val() || self.$referenceInput.attr('placeholder');
            var message = self.$messageInput.val();
            $.when.apply($, waitFor).then(function(result) {
                (new Model('signature.request')).call('initialize_new', [
                    self.templateID, signers, followers,
                    reference, subject, message
                ]).then(function(sr) {
                    self.do_notify(_t("Success"), _("Your signature request has been sent."));
                    self.do_action({
                        type: "ir.actions.client",
                        tag: 'website_sign.Document',
                        name: _t("New Document"),
                        context: {
                            id: sr.id,
                            token: sr.token,
                            create_uid: session.uid,
                            state: 'sent',
                        },
                    });
                }).always(function() {
                    self.close();
                });
            });
        },
    });

    var ShareTemplateDialog = Dialog.extend({
        template: 'website_sign.share_template_dialog',

        events: {
            'focus input': function(e) {
                $(e.target).select();
            },
        },

        init: function(parent, templateID, options) {
            options = options || {};
            options.title = options.title || _t("Multiple Signature Requests");
            options.size = options.size || "medium";

            this.templateID = templateID;
            this._super(parent, options);
        },

        start: function() {
            var self = this;

            var $linkInput = this.$('input').first();
            var linkStart = window.location.href.substr(0, window.location.href.indexOf('/web')) + '/sign/';

            var Templates = new Model('signature.request.template');
            return $.when(this._super(), Templates.call('share', [this.templateID]).then(function(link) {
                $linkInput.val((link)? (linkStart + link) : '');
                $linkInput.parent().toggle(!!link).next().toggle(!link);
            }));
        },
    });

    var AddFollowersDialog = Dialog.extend({
        template: "website_sign.add_followers_dialog",

        init: function(parent, requestID, options) {
            options = (options || {});
            options.title = options.title || _t("Send a copy to third parties");
            options.size = options.size || "medium";

            if(!options.buttons) {
                options.buttons = [];

                options.buttons.push({text: _t("Send"), classes: "btn-primary", click: function(e) {
                    var $button = $(e.target);
                    $button.prop('disabled', true);

                    var self = this;
                    processPartnersSelection(this.$select).then(function(partners) {
                        (new Model('signature.request')).call('add_followers', [self.requestID, partners])
                                                        .then(function() {
                                                            self.do_notify(_t("Success"), _t("A copy has been sent to the new followers."));
                                                        })
                                                        .always(function() {
                                                            self.close();
                                                        });
                    });
                }});

                options.buttons.push({text: _t("Discard"), close: true});
            }

            this._super(parent, options);

            this.requestID = requestID;
        },

        start: function() {
            this.$select = this.$('#o_sign_followers_select');
            setAsPartnerSelect(this.$select);
            return this._super.apply(this, arguments);
        },
    });

    PDFIframe.include({
        init: function() {
            this._super.apply(this, arguments);

            this.events = _.extend(this.events || {}, {
                'itemChange .o_sign_signature_item': function(e) {
                    this.updateSignatureItem($(e.target));
                    this.$iframe.trigger('templateChange');
                },

                'itemDelete .o_sign_signature_item': function(e) {
                    this.deleteSignatureItem($(e.target));
                    this.$iframe.trigger('templateChange');
                },

                'itemClone .o_sign_signature_item': function(e) {
                    var $target = $(e.target);
                    this.updateSignatureItem($target);

                    page_loop:
                    for(var i = 1 ; i <= this.nbPages ; i++) {
                        for(var j = 0 ; j < this.configuration[i].length ; j++) {
                            if(this.types[this.configuration[i][j].data('type')].type === 'signature') {
                                continue page_loop;
                            }
                        }

                        var $newElem = $target.clone(true);
                        this.enableCustom($newElem);
                        this.configuration[i].push($newElem);
                    }

                    this.deleteSignatureItem($target);
                    this.refreshSignatureItems();
                    this.$iframe.trigger('templateChange');
                },
            });
        },

        doPDFPostLoad: function() {
            var self = this;
            this.fullyLoaded.then(function() {
                if(self.editMode) {
                    if(self.$iframe.prop('disabled')) {
                        self.$('#viewer').fadeTo('slow', 0.75);
                        var $div = $('<div/>').css({
                            position: "absolute",
                            top: 0,
                            left: 0,
                            width: "100%",
                            height: "100%",
                            'z-index': 110,
                            opacity: 0.75
                        });
                        self.$('#viewer').css('position', 'relative').prepend($div);
                        $div.on('click mousedown mouseup mouveover mouseout', function(e) {
                            return false;
                        });
                    } else {
                        self.$hBarTop = $('<div/>');
                        self.$hBarBottom = $('<div/>');
                        self.$hBarTop.add(self.$hBarBottom).css({
                            position: 'absolute',
                            "border-top": "1px dashed orange",
                            width: "100%",
                            height: 0,
                            "z-index": 103,
                            left: 0
                        });
                        self.$vBarLeft = $('<div/>');
                        self.$vBarRight = $('<div/>');
                        self.$vBarLeft.add(self.$vBarRight).css({
                            position: 'absolute',
                            "border-left": "1px dashed orange",
                            width: 0,
                            height: "10000px",
                            "z-index": 103,
                            top: 0
                        });

                        var typesArr = $(Object.keys(self.types).map(function(id) { return self.types[id]; }));
                        var $fieldTypeButtons = $(core.qweb.render('website_sign.type_buttons', {signature_item_types: typesArr}));
                        self.$fieldTypeToolbar = $('<div/>').addClass('o_sign_field_type_toolbar');
                        self.$fieldTypeToolbar.prependTo(self.$('#viewerContainer'));
                        $fieldTypeButtons.appendTo(self.$fieldTypeToolbar).draggable({
                            cancel: false,
                            helper: function(e) {
                                var type = self.types[$(this).data('item-type-id')];
                                var $signatureItem = self.createSignatureItem(type, true, self.currentRole, 0, 0, type.default_width, type.default_height);

                                if(!e.ctrlKey) {
                                    self.$('.o_sign_signature_item').removeClass('ui-selected');
                                }
                                $signatureItem.addClass('o_sign_signature_item_to_add ui-selected');

                                self.$('.page').first().append($signatureItem);
                                self.updateSignatureItem($signatureItem);
                                $signatureItem.css('width', $signatureItem.css('width')).css('height', $signatureItem.css('height')); // Convert % to px
                                $signatureItem.detach();
                                
                                return $signatureItem;
                            }
                        });
                        $fieldTypeButtons.each(function(i, el) {
                            self.enableCustomBar($(el));
                        });

                        self.$('.page').droppable({
                            accept: '*',
                            tolerance: 'touch',
                            drop: function(e, ui) {
                                if(!ui.helper.hasClass('o_sign_signature_item_to_add')) {
                                    return true;
                                }

                                var $parent = $(e.target);
                                var pageNo = parseInt($parent.prop('id').substr('pageContainer'.length));

                                ui.helper.removeClass('o_sign_signature_item_to_add');
                                var $signatureItem = ui.helper.clone(true).removeClass().addClass('o_sign_signature_item o_sign_signature_item_required');

                                var posX = (ui.offset.left - $parent.find('.textLayer').offset().left) / $parent.innerWidth();
                                var posY = (ui.offset.top - $parent.find('.textLayer').offset().top) / $parent.innerHeight();
                                $signatureItem.data({posx: posX, posy: posY});

                                self.configuration[pageNo].push($signatureItem);
                                self.refreshSignatureItems();
                                self.updateSignatureItem($signatureItem);
                                self.enableCustom($signatureItem);

                                self.$iframe.trigger('templateChange');

                                if(self.types[$signatureItem.data('type')].type === 'initial') {
                                    (new InitialAllPagesDialog(self, self.parties)).open($signatureItem);
                                }

                                return false;
                            }
                        });

                        self.$('#viewer').selectable({
                            appendTo: self.$('body'), 
                            filter: '.o_sign_signature_item',
                        });

                        $(document).add(self.$el).on('keyup', function(e) {
                            if(e.which !== 46) {
                                return true;
                            }

                            self.$('.ui-selected').each(function(i, el) {
                                self.deleteSignatureItem($(el));
                            });
                            self.$iframe.trigger('templateChange');
                        });
                    }

                    self.$('.o_sign_signature_item').each(function(i, el) {
                        self.enableCustom($(el));
                    });
                }
            });

            this._super.apply(this, arguments);
        },

        enableCustom: function($signatureItem) {
            var self = this;

            $signatureItem.prop('title', this.types[$signatureItem.data('type')].name);

            var $configArea = $signatureItem.find('.o_sign_config_area');

            $configArea.find('.o_sign_responsible_display').off('mousedown').on('mousedown', function(e) {
                e.stopPropagation();
                self.$('.ui-selected').removeClass('ui-selected');
                $signatureItem.addClass('ui-selected');

                (new SignatureItemCustomDialog(self, self.parties)).open($signatureItem);
            });

            $configArea.find('.fa.fa-arrows').off('mouseup').on('mouseup', function(e) {
                if(!e.ctrlKey) {
                    self.$('.o_sign_signature_item').filter(function(i) {
                        return (this !== $signatureItem[0]);
                    }).removeClass('ui-selected');
                }
                $signatureItem.toggleClass('ui-selected');
            });

            $signatureItem.draggable({containment: "parent", handle: ".fa-arrows"}).resizable({containment: "parent"}).css('position', 'absolute');

            $signatureItem.off('dragstart resizestart').on('dragstart resizestart', function(e, ui) {
                if(!e.ctrlKey) {
                    self.$('.o_sign_signature_item').removeClass('ui-selected');
                }
                $signatureItem.addClass('ui-selected');
            });

            $signatureItem.off('dragstop').on('dragstop', function(e, ui) {
                $signatureItem.data({
                    posx: Math.round((ui.position.left / $signatureItem.parent().innerWidth())*1000)/1000,
                    posy: Math.round((ui.position.top / $signatureItem.parent().innerHeight())*1000)/1000,
                });
            });

            $signatureItem.off('resizestop').on('resizestop', function(e, ui) {
                $signatureItem.data({
                    width: Math.round(ui.size.width/$signatureItem.parent().innerWidth()*1000)/1000,
                    height: Math.round(ui.size.height/$signatureItem.parent().innerHeight()*1000)/1000,
                });
            });

            $signatureItem.on('dragstop resizestop', function(e, ui) {
                self.updateSignatureItem($signatureItem);
                self.$iframe.trigger('templateChange');
                $signatureItem.removeClass('ui-selected');
            });

            this.enableCustomBar($signatureItem);
        },

        enableCustomBar: function($item) {
            var self = this;

            $item.on('dragstart resizestart', function(e, ui) {
                start.call(self, ui.helper);
            });
            $item.find('.o_sign_config_area .fa.fa-arrows').on('mousedown', function(e) {
                start.call(self, $item);
                process.call(self, $item, $item.position());
            });
            $item.on('drag resize', function(e, ui) {
                process.call(self, ui.helper, ui.position);
            });
            $item.on('dragstop resizestop', function(e, ui) {
                end.call(self);
            });
            $item.find('.o_sign_config_area .fa.fa-arrows').on('mouseup', function(e) {
                end.call(self);
            });

            function start($helper) {
                this.$hBarTop.detach().insertAfter($helper).show();
                this.$hBarBottom.detach().insertAfter($helper).show();
                this.$vBarLeft.detach().insertAfter($helper).show();
                this.$vBarRight.detach().insertAfter($helper).show();
            }
            function process($helper, position) {
                this.$hBarTop.css('top', position.top);
                this.$hBarBottom.css('top', position.top+parseFloat($helper.css('height'))-1);
                this.$vBarLeft.css('left', position.left);
                this.$vBarRight.css('left', position.left+parseFloat($helper.css('width'))-1);
            }
            function end() {
                this.$hBarTop.hide();
                this.$hBarBottom.hide();
                this.$vBarLeft.hide();
                this.$vBarRight.hide();
            }
        },

        updateSignatureItem: function($signatureItem) {
            this._super.apply(this, arguments);

            if(this.editMode) {
                var responsibleName = this.parties[$signatureItem.data('responsible')].name;
                $signatureItem.find('.o_sign_responsible_display').html(responsibleName).prop('title', responsibleName);
            }
        },
    });

    var Template = Widget.extend(ControlPanelMixin, {
        className: "o_sign_template",

        events: {
            'click .fa-pencil': function(e) {
                this.$templateNameInput.focus().select();
            },

            'input .o_sign_template_name_input': function(e) {
                this.$templateNameInput.attr('size', this.$templateNameInput.val().length);
            },

            'change .o_sign_template_name_input': function(e) {
                this.saveTemplate();
                if(this.$templateNameInput.val() === "") {
                    this.$templateNameInput.val(this.initialTemplateName);
                }
            },

            'templateChange iframe.o_sign_pdf_iframe': function(e) {
                this.saveTemplate();
            },

            'click .o_sign_duplicate_signature_template': function(e) {
                this.saveTemplate(true);
            },
        },

        go_back_to_dashboard: function() {
            return this.do_action({
                type: "ir.actions.client",
                tag: 'website_sign.dashboard',
                name: _t("Digital Signatures Documents"),
            }, {
                clear_breadcrumbs: true,
            });
        },

        init: function(parent, options) {
            this._super.apply(this, arguments);

            if(options.context.id === undefined) {
                return;
            }

            this.templateID = options.context.id;
            this.rolesToChoose = {};

            var self = this;
            var $sendButton = $('<button/>', {html: _t("Send"), type: "button"})
                .addClass('btn btn-primary btn-sm')
                .on('click', function() {
                    self.prepareTemplateData();
                    (new CreateSignatureRequestDialog(self, self.templateID, self.rolesToChoose, self.$templateNameInput.val(), self.signature_request_template.attachment_id)).open();
                });
            var $shareButton = $('<button/>', {html: _t("Share"), type: "button"})
                .addClass('btn btn-default btn-sm')
                .on('click', function() {
                    (new ShareTemplateDialog(self, self.templateID)).open();
                });
            this.cp_content = {$buttons: $sendButton.add($shareButton)};
        },

        willStart: function() {
            if(this.templateID === undefined) {
                return this._super.apply(this, arguments);
            }
            return $.when(this._super(), this.perform_rpc());
        },

        perform_rpc: function() {
            var self = this;

            var IrAttachments = new Model('ir.attachment');
            var Templates = new Model('signature.request.template');
            var SignatureItems = new Model('signature.item');
            var Parties = new Model('signature.item.party');
            var ItemTypes = new Model('signature.item.type');

            var defTemplates = Templates.query()
                                        .filter([['id', '=', this.templateID]])
                                        .first()
                                        .then(prepare_template);

            var defParties = Parties.query()
                                    .all()
                                    .then(function(parties) { self.signature_item_parties = parties; });

            var defItemTypes = ItemTypes.query()
                                        .all()
                                        .then(function(types) { self.signature_item_types = types; });

            return $.when(defTemplates, defParties, defItemTypes);

            function prepare_template(template) {
                self.signature_request_template = template;
                self.has_signature_requests = (template.signature_request_ids.length > 0);

                var defSignatureItems = SignatureItems.query()
                                                      .filter([['template_id', '=', template.id]])
                                                      .all()
                                                      .then(function(signature_items) { self.signature_items = signature_items; });

                var defIrAttachments = IrAttachments.query(['mimetype', 'name', 'datas_fname'])
                                                    .filter([['id', '=', template.attachment_id[0]]])
                                                    .first()
                                                    .then(function(attachment) {
                                                        self.signature_request_template.attachment_id = attachment;
                                                        self.isPDF = (attachment.mimetype.indexOf('pdf') > -1);
                                                    });

                return $.when(defSignatureItems, defIrAttachments);
            }
        },

        start: function() {
            if(this.templateID === undefined) {
                return this.go_back_to_dashboard();
            }
            this.initialize_content();
            if(this.$('iframe').length) {
                core.bus.on('DOM_updated', this, init_iframe);
            }
            return this._super();

            function init_iframe() {
                if(this.$el.parents('html').length) {
                    var self = this;
                    framework.blockUI({overlayCSS: {opacity: 0}, blockMsgClass: 'o_hidden'});
                    this.iframeWidget = new PDFIframe(this,
                                                      '/web/binary/image?model=ir.attachment&field=datas&id=' + this.signature_request_template.attachment_id.id,
                                                      true,
                                                      {
                                                          parties: this.signature_item_parties,
                                                          types: this.signature_item_types,
                                                          signatureItems: this.signature_items,
                                                      });
                    return this.iframeWidget.attachTo(this.$('iframe')).then(function() {
                        framework.unblockUI();
                        self.iframeWidget.currentRole = self.signature_item_parties[0].id;
                    });
                }
            }
        },

        initialize_content: function() {
            this.$el.append(core.qweb.render('website_sign.template', {widget: this}));

            this.$('iframe,.o_sign_template_name_input').prop('disabled', this.has_signature_requests);

            this.$templateNameInput = this.$('.o_sign_template_name_input').first();
            this.$templateNameInput.trigger('input');
            this.initialTemplateName = this.$templateNameInput.val();

            this.refresh_cp();
        },

        do_show: function() {
            this._super();

            var self = this; // The iFrame cannot be detached, so we 'restart' the widget
            return this.perform_rpc().then(function() {
                if(self.iframeWidget) {
                    self.iframeWidget.destroy();
                    self.iframeWidget = undefined;
                }
                self.$el.empty();
                self.initialize_content();
            });
        },

        refresh_cp: function() {
            this.update_control_panel({
                breadcrumbs: this.getParent().get_breadcrumbs(),
                cp_content: this.cp_content
            });
        },

        prepareTemplateData: function() {
            this.rolesToChoose = {};
            var data = {}, newId = 0;
            var configuration = (this.iframeWidget)? this.iframeWidget.configuration : {};
            for(var page in configuration) {
                for(var i = 0 ; i < configuration[page].length ; i++) {
                    var resp = configuration[page][i].data('responsible');

                    data[configuration[page][i].data('item-id') || (newId--)] = {
                        'type_id': configuration[page][i].data('type'),
                        'required': configuration[page][i].data('required'),
                        'responsible_id': resp,
                        'page': page,
                        'posX': configuration[page][i].data('posx'),
                        'posY': configuration[page][i].data('posy'),
                        'width': configuration[page][i].data('width'),
                        'height': configuration[page][i].data('height'),
                    };

                    this.rolesToChoose[resp] = this.iframeWidget.parties[resp].name;
                }
            }
            return data;
        },

        saveTemplate: function(duplicate) {
            duplicate = (duplicate === undefined)? false : duplicate;

            var data = this.prepareTemplateData();
            var $majInfo = this.$('.o_sign_template_saved_info').first();

            var self = this;
            var Template = new Model('signature.request.template');
            Template.call('update_from_pdfviewer', [this.templateID, !!duplicate, data, this.$templateNameInput.val() || this.initialTemplateName])
                    .then(function(templateID) {
                        if(!templateID) {
                            Dialog.alert(self, _t('Somebody is already filling a document which uses this template'), {
                                confirm_callback: function() {
                                    self.go_back_to_dashboard();
                                },
                            });
                        }

                        if(duplicate) {
                            self.do_action({
                                type: "ir.actions.client",
                                tag: 'website_sign.Template',
                                name: _t("Duplicated Template"),
                                context: {
                                    id: templateID,
                                },
                            });
                        } else {
                            $majInfo.stop().css('opacity', 1).animate({'opacity': 0}, 1500);
                        }
                    });
        },
    });

    var DocumentBackend = Widget.extend(ControlPanelMixin, {
        className: 'o_sign_document',
        events: {
            'click .o_sign_resend_access_button.fa': function(e) {
                var $envelope = $(e.target);
                $envelope.removeClass('fa fa-envelope').html('...');
                (new Model('signature.request.item')).call('resend_access', [parseInt($envelope.parent('.o_sign_signer_status').data('id'))])
                                                     .then(function() { $envelope.html(_t("Resent !")); });
            },
        },

        go_back_to_dashboard: function() {
            return this.do_action({
                type: "ir.actions.client",
                tag: 'website_sign.dashboard',
                name: _t("Digital Signatures Documents"),
            }, {
                clear_breadcrumbs: true,
            });
        },

        init: function(parent, options) {
            this._super.apply(this, arguments);

            if(options.context.id === undefined) {
                return;
            }

            this.documentID = options.context.id;
            this.token = options.context.token;
            this.create_uid = options.context.create_uid;
            this.state = options.context.state;

            var self = this;

            var $downloadButton = $('<a/>', {html: _t("Download Document")}).addClass('btn btn-sm btn-primary o_hidden');
            var $historyButton = $('<button/>', {html: _t("View History"), type: "button"}).addClass('btn btn-sm btn-default')
                .on('click', function() {
                    if(self.documentPage) {
                        self.documentPage.openChatter();
                    }
                });
            var $addFollowersButton = $('<button/>', {html: _t("Send a copy"), type: "button"}).addClass('btn btn-sm btn-default o_hidden')
                .on('click', function() {
                    (new AddFollowersDialog(self, self.documentID)).open();
                });
            var $cancelButton = $('<button/>', {html: _t("Cancel Request"), type: "button"}).addClass('btn btn-sm btn-default o_hidden')
                .on('click', function() {
                    (new Model('signature.request')).call('cancel', [self.documentID]).then(function() {
                        self.go_back_to_dashboard();
                    });
                });
            this.cp_content = {$buttons: $downloadButton.add($historyButton).add($addFollowersButton).add($cancelButton)};
        },

        start: function() {
            var self = this;

            if(this.documentID === undefined) {
                return this.go_back_to_dashboard();
            }

            this.is_author = (this.create_uid == session.uid);
            this.is_sent = (this.state === 'sent');

            return $.when(this._super(), ajax.jsonRpc('/sign/get_document/' + this.documentID + '/' + this.token, 'call', {'message': this.message}).then(function(html) {
                self.$el.append($(html.trim()));

                var $cols = self.$('.col-md-4').toggleClass('col-md-6 col-md-4');
                var $buttonsContainer = $cols.first().remove();

                var url = $buttonsContainer.find('.o_sign_download_document_button').attr('href');
                self.cp_content.$buttons.eq(0).attr('href', url).toggleClass('o_hidden', !url);
                self.cp_content.$buttons.eq(2).toggleClass('o_hidden', !self.is_author);
                self.cp_content.$buttons.eq(3).toggleClass('o_hidden', !self.is_author || !self.is_sent);

                if(self.is_author && self.is_sent) {
                    self.$('.o_sign_signer_status').each(function(i, el) {
                        $(el).prepend($('<button/>', {
                            type: 'button',
                            title: _t("Resend the invitation"),
                        }).addClass('o_sign_resend_access_button btn btn-link fa fa-envelope pull-right'));
                    });
                }
                
                var init_page = function() {
                    if(self.$el.parents('html').length) {
                        self.refresh_cp();
                        framework.blockUI({overlayCSS: {opacity: 0}, blockMsgClass: 'o_hidden'});
                        var def;
                        if(!self.documentPage) {
                            self.documentPage = new Document(self);
                            def = self.documentPage.attachTo(self.$el);
                        } else {
                            def = self.documentPage.initialize_iframe();
                        }
                        def.then(function() {
                            framework.unblockUI();
                        });
                    }
                };
                core.bus.on('DOM_updated', null, init_page);
            }));
        },

        refresh_cp: function() {
            this.update_control_panel({
                breadcrumbs: this.getParent().get_breadcrumbs(),
                cp_content: this.cp_content
            });
        },
    });

    core.action_registry.add('website_sign.Template', Template);
    core.action_registry.add('website_sign.Document', DocumentBackend);

    function getResponsibleSelectConfiguration(parties) {
        if(getResponsibleSelectConfiguration.configuration === undefined) {
            var select2Options = {
                placeholder: _t("Select the responsible"),
                allowClear: false,

                formatResult: function(data, resultElem, searchObj) {
                    if(!data.text) {
                        $(data.element[0]).data('create_name', searchObj.term);
                        return _t("Create: \"") + searchObj.term + "\"";
                    }
                    return data.text;
                },

                formatSelection: function(data) {
                    if(!data.text) {
                        return $(data.element[0]).data('create_name');
                    }
                    return data.text;
                },

                matcher: function(search, data) {
                    if(!data) {
                        return (search.length > 0);
                    }
                    return (data.toUpperCase().indexOf(search.toUpperCase()) > -1);
                }
            };

            var selectChangeHandler = function(e) {
                var $select = $(e.target), $option = $(e.added.element[0]);

                var resp = parseInt($option.val());
                var name = $option.html() || $option.data('create_name');
                
                if(resp >= 0 || !name) {
                    return false;
                }

                (new Model('signature.item.party')).call('add', [name]).then(process_party);

                function process_party(partyID) {
                    parties[partyID] = {id: partyID, name: name};
                    getResponsibleSelectConfiguration.configuration = undefined;
                    setAsResponsibleSelect($select, partyID, parties);
                }
            };

            var $responsibleSelect = $('<select/>').append($('<option/>'));
            for(var id in parties) {
                $responsibleSelect.append($('<option/>', {
                    value: parseInt(id),
                    html: parties[id].name,
                }));
            }
            $responsibleSelect.append($('<option/>', {value: -1}));

            getResponsibleSelectConfiguration.configuration = {
                html: $responsibleSelect.html(),
                options: select2Options,
                handler: selectChangeHandler,
            };
        }

        return getResponsibleSelectConfiguration.configuration;
    }

    function setAsResponsibleSelect($select, selected, parties) {
        var configuration = getResponsibleSelectConfiguration(parties);

        $select.select2('destroy');
        $select.html(configuration.html).addClass('form-control');
        if(selected !== undefined) {
            $select.val(selected);
        }
        $select.select2(configuration.options);
        $select.off('change').on('change', configuration.handler);
    }

    function getPartnerSelectConfiguration() {
        if(getPartnerSelectConfiguration.def === undefined) {
            getPartnerSelectConfiguration.def = new $.Deferred();

            var select2Options = {
                allowClear: true,

                formatResult: function(data, resultElem, searchObj) {
                    var partner = $.parseJSON(data.text);
                    if($.isEmptyObject(partner)) {
                        var $elem = $(data.element[0]);

                        var partnerMatch = searchObj.term.match(/(?:\s|\()*(((?:\w|-|\.)+)@(?:\w|-)+\.(?:\w|-)+)(?:\s|\))*/);
                        if(!partnerMatch || partnerMatch[1] === undefined) {
                            $elem.removeData('name mail');
                            return $("<div/>", {html: _t("Create: \"") + searchObj.term + "\""})
                                    .addClass('o_sign_create_partner')
                                    .append($("<span/>").addClass('fa fa-exclamation-circle'))
                                    .append($("<span/>", {html: _t("Enter email (and name if you want)")}).addClass('small'));
                        } else {
                            var index = searchObj.term.indexOf(partnerMatch[0]);
                            var name = searchObj.term.substr(0, index) + " " + searchObj.term.substr(index + partnerMatch[0].length);
                            if(name === " ") {
                                name = partnerMatch[2];
                            }

                            $elem.data({name: name, mail: partnerMatch[1]});
                            return $("<div/>", {html: _t("Create: \"") + $elem.data('name') + " (" + $elem.data('mail') + ")" + "\""})
                                .addClass('o_sign_create_partner')
                                .append($("<span/>").addClass('fa fa-check-circle'));
                        }
                    }

                    return $("<div/>", {html: ((partner['new'])? _t("New: ") : "") + partner.name + " (" + partner.email + ")"}).addClass('o_sign_add_partner');
                },

                formatSelection: function(data) {
                    var partner = $.parseJSON(data.text);
                    if($.isEmptyObject(partner)) {
                        return _t("Error");
                    }

                    return ((partner['new'])? _t("New: ") : "") + partner.name + " (" + partner.email + ")";
                },

                matcher: function(search, data) {
                    var partner = $.parseJSON(data);
                    if($.isEmptyObject(partner)) {
                        return (search.length > 0);
                    }

                    var searches = search.toUpperCase().split(/[ ()]/);
                    for(var i = 0 ; i < searches.length ; i++) {
                        if(partner['email'].toUpperCase().indexOf(searches[i]) < 0 && partner['name'].toUpperCase().indexOf(searches[i]) < 0) {
                            return false;
                        }
                    }
                    return true;
                }
            };

            var selectChangeHandler = function(e) {
                if(e.added && e.added.element.length > 0) {
                    var $option = $(e.added.element[0]);
                    var $select = $option.parent();
                    if(parseInt($option.val()) !== 0) {
                        return true;
                    }

                    setTimeout(function() {
                        $select.select2("destroy");

                        if(!$option.data('mail')) {
                            $option.prop('selected', false);
                        } else {
                            if(!$select.data('newNumber')) {
                                $select.data('newNumber', 0);
                            }
                            var newNumber = $select.data('newNumber') - 1;
                            $select.data('newNumber', newNumber);

                            $option.val(newNumber);
                            $option.html('{"name": "' + $option.data('name') + '", "email": "' + $option.data('mail') + '", "new": "1"}');

                            var $newOption = $('<option/>', {
                                value: 0,
                                html: "{}"
                            });
                            $select.find('option').filter(':last').after($newOption);
                        }

                        $select.select2(select2Options);
                    }, 0);
                } else if(e.removed && e.removed.element.length > 0) {
                    var $option = $(e.removed.element[0]);
                    var $select = $option.parent();
                    if(parseInt($option.val()) >= 0) {
                        return true;
                    }

                    setTimeout(function() {
                        $select.select2("destroy");
                        $select.find('option[value=' + $option.val() + ']').remove();
                        $select.select2(select2Options);
                    }, 0);
                }
            };

            (new Model('res.partner')).query(['name', 'email'])
                                      .filter([['email', '!=', '']])
                                      .all()
                                      .then(process_partners);
        }

        return getPartnerSelectConfiguration.def;

        function process_partners(data) {
            var $partnerSelect = $('<select><option/></select>');
            for(var i = 0 ; i < data.length ; i++) {
                $partnerSelect.append($('<option/>', {
                    value: data[i]['id'],
                    html: JSON.stringify(data[i])
                }));
            }
            $partnerSelect.append($('<option/>', {
                value: 0,
                html: "{}",
            }));

            getPartnerSelectConfiguration.def.resolve($partnerSelect.html(), select2Options, selectChangeHandler);
        }
    }

    function setAsPartnerSelect($select) {
        return getPartnerSelectConfiguration().then(function(selectHTML, select2Options, selectChangeHandler) {
            $select.select2('destroy');
            $select.html(selectHTML).addClass('form-control');
            $select.select2(select2Options);
            $select.off('change').on('change', selectChangeHandler);
        });
    }

    function processPartnersSelection($select) {
        var partnerIDs = $select.val();
        if(!partnerIDs || partnerIDs.length <= 0) {
            return $.Deferred().resolve([]);
        }

        if(typeof partnerIDs === 'string') {
            partnerIDs = [parseInt(partnerIDs)];
        }

        var partners = [];
        var partnersToCreate = [];
        $(partnerIDs).each(function(i, partnerID) {
            partnerID = parseInt(partnerID);
            if(partnerID < 0) {
                var partnerInfo = $.parseJSON($select.find('option[value=' + partnerID + ']').html());
                partnersToCreate.push([partnerInfo.name.trim(), partnerInfo.email.trim()]);
            } else if(partnerID > 0) {
                partners.push(partnerID);
            }
        });

        var def = $.Deferred();
        if(partnersToCreate.length > 0) {
            ajax.jsonRpc("/sign/new_partners", 'call', {
                'partners': partnersToCreate,
            }).then(function(pIDs) {
                def.resolve(partners.concat(pIDs));
            });
        } else {
            def.resolve(partners);
        }

        return def;
    }
});
