odoo.define('account_online_sync.acc_config_widget', function(require) {
"use strict";

var core = require('web.core');
var form_relational = require('web.form_relational');
var common = require('web.form_common');
var Dialog = require('web.Dialog');
var Model = require('web.Model');
var framework = require('web.framework');
var time = require('web.time');
var datepicker = require('web.datepicker');
var QWeb = core.qweb;
var _t = core._t;

/**
 * Widget that will serve as base for plaid and yodlee widget, this widget can not work alone!
 * This widget create a dialog to allow user to configure an online account with yodlee or plaid interface
 */
var OnlineSynchAccountConfigurationWidget = form_relational.FieldMany2One.extend({

    post_process_connection_result: function(resp_json) {
        var self = this;
        this.config_template = 'OnlineSynchLoginTemplate';
        this.config_template_buttons = [
                { text: _t("Continue"), click: function() { self.hide_error(); self.process_next_step(); },
                 classes: 'js_process_next_step btn-primary'},
                { text: _t("Continue"), click: function() { self.hide_error(); self.process_mfa_step(); },
                 classes: 'js_process_mfa_step hide btn-primary'},
                { text: _t("Finish"), click: function() { self.hide_error(); self.complete_process(); },
                 classes: 'js_conclude_configuration hide btn-primary'},
                { text: _t("Cancel"), click: function() { self.configurator_wizard.close(); }}
            ];
        //Must be implemented by children widget
        this.config_template_data = {}
    },

    check_empty_field: function() {
        var self = this;
        var $inputs = this.configurator_wizard.$el.find('input[optional="false"]:not([type="radio"])');
        var $radios = this.configurator_wizard.$el.find('input[type="radio"]');
        var $selects = this.configurator_wizard.$el.find('select');
        var hasError = false;
        if ($radios.length > 0) {
            if (this.configurator_wizard.$el.find('input[type="radio"]:checked').length === 0) {
                hasError = true;
            }
        }
        if ($inputs.length > 0) {
            $.each($inputs, function(k,v){
                $(v).parent().removeClass('has-error');
                if (v.value === undefined || v.value === ''){
                    hasError = true;
                    $(v).parent().addClass('has-error');
                }
            });
        }
        if ($selects.length > 0) {
            $.each($inputs, function(k,v){
                $(v).parent().removeClass('has-error');
                if (v.value === undefined || v.value === ''){
                    hasError = true;
                    $(v).parent().addClass('has-error');
                }
            });
        }
        if (hasError) {
            this.show_error("Error: please fill all the fields");
        }
        return hasError;
    },

    process_next_step: function() {
        //Call function to check empty field
        if (this.check_empty_field()) {
            return false;
        }
        return true;
        //To be implemented by children widget
    },

    process_mfa_step: function() {
        if (this.check_empty_field()) {
            return false;
        }
        return true;
        //To be implemented by children widget
    },

    complete_process: function(){
        if (this.check_empty_field()) {
            return false;
        }
        return true;
        //To be implemented by children widget
    },

    show_error: function(message, errorCode) {
        framework.unblockUI();
        this.configurator_wizard.$el.find('.js_online_sync_wait').hide();
        if (message === false) {
            message = "An error occured!";
        }
        if (errorCode != undefined) {
            message = message + " (error Code: "+errorCode+")";
        }
        $(this.configurator_wizard.$el).find('.error_msg').text(message)
        $(this.configurator_wizard.$el).find('.error').removeClass('hide');
    },

    hide_error: function() {
        $(this.configurator_wizard.$el).find('.error').addClass('hide');
    },

    launch_configurator_wizard: function(result) {
        var self = this;
        //Process json_result and open dialog
        this.post_process_connection_result(result);
        this.configurator_wizard = new Dialog(this, {
              title: _t("Configure Online Account"),
              $content: QWeb.render(self.config_template, self.config_template_data),
              buttons: self.config_template_buttons,
              size: 'medium',
            });
        this.configurator_wizard.open();
    },

    fetch_site_info: function() {
        //Store journal_id and online_id globally since we will need them in most request
        this.online_institution_id = this.view.fields.online_institution_id.get("value");
        this.id = this.view.fields.journal_id.get("value");
        this.online_id = this.view.fields.online_id.get("value");
        //Call to server must be implemented by children widget
    },

    is_false: function() {
        return false;
    },

    render_value: function() {
        var self = this;
        var res = this._super();
        if (this.$el.find('.js_configure_online_account').length === 0){
            this.$el.append('<a href="#" class="js_configure_online_account">(-> Configure)</a>');
            this.$('.js_configure_online_account').click(function(event){
                //When clicking widget, ensure that view is not in edit to prevent inconsistance with server value
                //Also preventdefault to prevent changing url with an incorrect hash
                event.preventDefault();
                event.stopPropagation();
                self.view.save().then(function(result){
                    self.view.to_view_mode();
                    
                    var fetch_site_info = self.fetch_site_info()
                        .then(function(result){
                            self.launch_configurator_wizard(JSON.parse(result));
                        });
                });
            });
        }
        return res;
    },

    attach_datepicker: function() {
        var current_date = new moment();
        var dp = new datepicker.DateWidget(this);
        dp.appendTo(this.configurator_wizard.$el.find('.js_online_sync_date'));
        dp.set_value(current_date.subtract(15, 'days'));
        this.datepicker = dp;
    },
});

return {
    OnlineSynchAccountConfigurationWidget: OnlineSynchAccountConfigurationWidget,
}

});
