odoo.define('web.UserMenu', function (require) {
"use strict";

var core = require('web.core');
var Dialog = require('web.Dialog');
var Model = require('web.Model');
var session = require('web.session');
var Widget = require('web.Widget');

var _t = core._t;
var QWeb = core.qweb;

var UserMenu = Widget.extend({
    template: "UserMenu",
    init: function(parent) {
        this._super(parent);
        this.update_promise = $.Deferred().resolve();
    },
    start: function() {
        var self = this;
        this.$el.on('click', '.dropdown-menu li a[data-menu]', function(ev) {
            ev.preventDefault();
            var f = self['on_menu_' + $(this).data('menu')];
            if (f) {
                f($(this));
            }
        });
        return this._super.apply(this, arguments).then(function () {
            self.do_update();
        });
    },
    do_update: function () {
        var self = this;
        var fct = function() {
            var $avatar = self.$('.oe_topbar_avatar');
            $avatar.attr('src', $avatar.data('default-src'));
            if(!session.uid) {
                return;
            }
            var func = new Model("res.users").get_func("read");
            return self.alive(func(session.uid, ["name", "company_id"])).then(function(res) {
                var topbar_name = res.name;
                if(session.debug) {
                    topbar_name = _.str.sprintf("%s (%s)", topbar_name, session.db);
                }
                if(res.company_id[0] > 1) {
                    topbar_name = _.str.sprintf("%s (%s)", topbar_name, res.company_id[1]);
                }
                self.$('.oe_topbar_name').text(topbar_name);

                var avatar_src = session.url('/web/image', {model:'res.users', field: 'image_small', id: session.uid});
                $avatar.attr('src', avatar_src);
            });
        };
        this.update_promise = this.update_promise.then(fct, fct);
    },
    on_menu_logout: function() {
        this.do_action('logout');
    },
    on_menu_settings: function() {
        var self = this;
        return self.rpc("/web/action/load", { action_id: "base.action_res_users_my" }).then(function(result) {
            result.res_id = session.uid;
            self.do_action(result);
            return result;
        });
    },
    on_menu_account: function() {
        var P = new Model('ir.config_parameter');
        P.call('get_param', ['database.uuid']).then(function(dbuuid) {
            var state = {
                        'd': session.db,
                        'u': window.location.protocol + '//' + window.location.host,
                    };
            var params = {
                response_type: 'token',
                client_id: dbuuid || '',
                state: JSON.stringify(state),
                scope: 'userinfo',
            };
            window.location.href = 'https://accounts.odoo.com/oauth2/auth?'+$.param(params);
        }).fail(function(result, ev){
            ev.preventDefault();
            window.location.href = 'https://accounts.odoo.com/account';
        });
    },
});

return UserMenu;
});
