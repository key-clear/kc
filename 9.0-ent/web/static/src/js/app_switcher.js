odoo.define('web.AppSwitcher', function (require) {
"use strict";

var core = require('web.core');
var Widget = require('web.Widget');
var UserMenu = require('web.UserMenu');

var AppSwitcher = Widget.extend({
    template: 'AppSwitcher',
    events: {
        'click .o_action_app': 'on_app_click',
    },
    init: function (parent, menu_data) {
        this._super.apply(this, arguments);
        this.menu_data = menu_data;
    },
    willStart: function() {
        // Force the background image to be in the browser cache before the
        // stylesheet requests it
        var bg_loaded = $.Deferred();
        var bg = new Image();
        bg.onload = function () {
            bg_loaded.resolve();
        };
        bg.src = '/web/static/src/img/application-switcher-bg.jpg';

        return $.when(this._super.apply(this, arguments), bg_loaded);
    },
    on_app_click: function (ev) {
        ev.preventDefault();
        this.trigger_up('app_clicked', {
            menu_id: $(ev.currentTarget).data('menu'),
            action_id: $(ev.currentTarget).data('action-id'),
        });
    },
});

var AppSwitcherNavbar = Widget.extend({
    template: 'AppSwitcherNavbar',
    events: {
        'click .o_back_button': function (ev) {
            ev.preventDefault();
            this.trigger_up('hide_app_switcher');
        }
    },
    on_attach_callback: function(options) {
        this.toggle_back_button(options && options.display_back_button);
        // Hide the app switcher when pressing the escape key
        core.bus.on('keyup', this, this._hide_app_switcher);
    },
    on_detach_callback: function() {
        // Unbind the event handler when the navbar is detached from the DOM
        core.bus.off('keyup', this, this._hide_app_switcher);
    },
    init: function () {
        this._super.apply(this, arguments);
        this.backbutton_displayed = false;
    },
    start: function () {
        var self = this;
        var user_menu = new UserMenu(this);
        return this._super.apply(this, arguments).then(function () {
            user_menu.appendTo(self.$('.o_appswitcher_navbar_systray'));
        });
    },
    toggle_back_button: function (display) {
        this.$('.o_back_button').toggleClass('hidden', !display);
        this.backbutton_displayed = display;
    },
    _hide_app_switcher: function (ev) {
        if (ev.keyCode === 27 && this.backbutton_displayed === true) {
            this.trigger_up('hide_app_switcher');
        }
    },
});

return {
    AppSwitcher: AppSwitcher,
    AppSwitcherNavbar: AppSwitcherNavbar,
};

});
