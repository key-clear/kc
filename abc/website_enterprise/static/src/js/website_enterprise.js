odoo.define('website.app_switcher', function(require) {
    'use strict';

    var ajax = require('web.ajax');
    var appswitcher = require('web.AppSwitcher');
    var core = require('web.core');
    var Model = require('web.Model');
    var session = require('web.session');
    var UserMenu = require('web.UserMenu');
    var website = require('website.website');

    website.TopBar.include({
        start: function() {
            var self = this;
            return this._super.apply(this, arguments).then(function() {
                var $body = $('body');
                var $body_contents = $body.contents();
                var loading = false;

                self.$('.o_menu_toggle').on('click', function(e) {
                    e.preventDefault();
                    if(loading) {
                        return false;
                    }

                    // When you load the menu for the first time, it takes at least 3sec.
                    // We add a spinner for the user to understand the loading.
                    var icon_switcher = $(e.currentTarget).find('span.fa');
                    icon_switcher
                        .removeClass('fa-th')
                        .addClass('fa-spin fa-spinner');

                    loading = true;
                    if(!self.app_switcher) {
                        session.session_reload().then(function() { // hack to get uid
                            var Menus = new Model('ir.ui.menu');
                            return Menus.call('load_menus_root').then(function(menu_data) {
                                for(var i = 0 ; i < menu_data.children.length ; i++) {
                                    menu_data.children[i]['href'] = '/web' + ((session.debug)? '?debug' : '') + '#menu_id=' + menu_data.children[i].id + '&action='
                                                                    + ((menu_data.children[i].action)? menu_data.children[i].action.split(',')[1] : '');
                                }

                                self.app_switcher_navbar = new appswitcher.AppSwitcherNavbar(self);
                                self.app_switcher = new appswitcher.AppSwitcher(self, menu_data.children);

                                var defs = [];
                                defs.push(self.app_switcher.prependTo(document.createDocumentFragment()));
                                defs.push(self.app_switcher_navbar.prependTo(document.createDocumentFragment()));
                                return $.when.apply($, defs);
                            }).then(toggle_content);
                        });
                    } else {
                        toggle_content();
                    }

                    function toggle_content() {
                        icon_switcher
                            .addClass('fa-th')
                            .removeClass('fa-spin fa-spinner');

                        self.app_switcher_navbar.toggle_back_button(true);
                        self.app_switcher.$el.prependTo($body);
                        self.app_switcher_navbar.$el.prependTo($body);
                        $body_contents.detach();
                        $body.addClass('o_web_client');
                        loading = false;
                    }
                });

                self.on('hide_app_switcher', self, function() {
                    if(self.app_switcher) {
                        self.app_switcher.$el.detach();
                        self.app_switcher_navbar.$el.detach();
                        $body.removeClass('o_web_client');
                        $body_contents.appendTo($body);
                    }
                });
            });
        },
    });

    UserMenu.include({
        on_menu_logout: function() {
            window.location.href = "/web/session/logout";
        },

        on_menu_settings: function() {
            return this._super.apply(this, arguments).then(function(action) {
                window.location.href = "/web#id=" + action.res_id + "&model=" + action.res_model + "&action=" + action.id;
            });
        },
    });
});
