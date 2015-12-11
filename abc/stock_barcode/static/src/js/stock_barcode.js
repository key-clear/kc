odoo.define('stock_barcode.MainMenu', function (require) {
"use strict";

var core = require('web.core');
var Model = require('web.Model');
var Widget = require('web.Widget');
var Session = require('web.session');
var BarcodeHandlerMixin = require('barcodes.BarcodeHandlerMixin');

var MainMenu = Widget.extend(BarcodeHandlerMixin, {
    template: 'main_menu',

    events: {
        "click .button_operations": function(){ this.do_action('stock_barcode.stock_picking_type_action_kanban') },
        "click .button_inventory": function(){ this.open_inventory() },
    },

    on_attach_callback: function() {
        this.start_listening();
    },

    on_detach_callback: function() {
        this.stop_listening();
    },

    on_barcode_scanned: function(barcode) {
        var self = this;
        Session.rpc('/stock_barcode/scan_from_main_menu', {
            barcode: barcode,
        }).then(function(result) {
            if (result.action) {
                self.do_action(result.action);
            } else if (result.warning) {
                self.do_warn(result.warning);
            }
        });
    },

    open_inventory: function() {
        var self = this;
        return new Model("stock.inventory")
            .call("open_new_inventory", [])
            .then(function(result) {
                self.do_action(result);
            });
    },
});

core.action_registry.add('stock_barcode_main_menu', MainMenu);

return {
    MainMenu: MainMenu,
};

});
