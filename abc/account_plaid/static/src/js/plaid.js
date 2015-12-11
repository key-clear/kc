odoo.define('account_plaid.acc_config_widget', function(require) {
"use strict";

var core = require('web.core');
var common = require('web.form_common');
var Model = require('web.Model');
var online_sync = require('account_online_sync.acc_config_widget');
var QWeb = core.qweb;
var _t = core._t;


var PlaidAccountConfigurationWidget = online_sync.OnlineSynchAccountConfigurationWidget.extend({

    post_process_connection_result: function(resp_json) {
        this._super();
        //process login form
        var inputs_vals = []
        this.response = {'type': resp_json.type, 'options': '{"login_only": true, "list": true}'}
        if (resp_json.credentials.username !== undefined) {
            inputs_vals = inputs_vals.concat({displayName: resp_json.credentials.username,
                fieldType: 'text',
                indexResponse: 'username',
                maxlength: -1,
                optional: false,});
        }
        if (resp_json.credentials.password !== undefined) {
            inputs_vals = inputs_vals.concat({displayName: resp_json.credentials.password,
                fieldType: 'password',
                indexResponse: 'password',
                maxlength: -1,
                optional: false,});
        }
        if (resp_json.credentials.pin !== undefined) {
            inputs_vals = inputs_vals.concat({displayName: resp_json.credentials.pin,
                fieldType: 'text',
                indexResponse: 'pin',
                maxlength: -1,
                optional: false,});
        }
        this.config_template_data = {inputs: inputs_vals};
    },

    parse_json_result: function(resp_json) {
        if (resp_json.status_code === 200){
            //Login correct, show account
            this.show_account_selector(resp_json);
        }
        else if (resp_json.status_code === 201) {
            //Show MFA
            this.show_mfa_to_user(resp_json);
        }
        else if (resp_json.status_code >= 400){
            this.show_error(resp_json.message, resp_json.code);
        }
        else {
            this.show_error("ERROR: an error has occured, HTTP status code: "+resp_json.status_code);
        }
    },

    process_next_step: function() {
        var self = this;
        if (this._super()){
            //execute code only if super returns true meaning no error found
            //Get response
            this.response['username'] = $(".js_online_sync_input[id='username']").val();
            this.response['password'] = $(".js_online_sync_input[id='password']").val();
            if ($(".js_online_sync_input[id='password']").length > 0){
                this.response['pin'] = $(".js_online_sync_input[id='pin']").val();
            }
            var request = new Model('account.journal').call('fetch', [[this.id], '/connect', this.online_type, this.response])
                .then(function(result){
                    var resp_json = JSON.parse(result);
                    self.parse_json_result(resp_json);
                });
        }
    },

    show_mfa_to_user: function(resp_json) {
        var self = this;
        var choices = [];
        var qdict = {type: resp_json.type}
        this.token = resp_json.access_token;
        if (resp_json.type === 'list') {
            $.each(resp_json.mfa, function(k,v){
                choices = choices.concat({mask: v.mask, type: v.type});
            });
        }
        else if (resp_json.type === 'questions') {
            $.each(resp_json.mfa, function(k,v){
                choices = choices.concat({question: v.question});
            });
        }
        else if (resp_json.type === 'selections') {
            $.each(resp_json.mfa, function(k,v){
                choices = choices.concat({question: v.question, answers: v.answers});
            });
        }
        else {
            qdict['name'] = resp_json.mfa.message + " (Enter code in area below)";
        }
        qdict['choices'] = choices;
        this.configurator_wizard.$footer.find('.js_process_next_step').hide();
        this.configurator_wizard.$footer.find('.js_process_mfa_step').removeClass('hide');
        this.configurator_wizard.$el.find('.js_online_sync_form').html(QWeb.render('PlaidMFAConfigurator', qdict));
    },

    process_mfa_step: function() {
        var self = this;
        if (this._super()) {
            var params = {'access_token': this.token, 'options': '{"login_only": true, "list": true}'}
            if ($('input[name="mfa-selection"]').length > 0){
                params['options'] = '{"send_method": {"mask": "'+ $('input[name="mfa-selection"]:checked').attr('mask') +'"}}';
            }
            else {
                //Get all input with information
                var $answers = $('.js_plaid_answer');
                var user_reply = [];
                if ($answers.length === 1){
                    params['mfa'] = $answers.val();
                }
                else {
                    $.each($answers, function(k,v){
                        user_reply = user_reply.concat(v.val());
                    });
                    params['mfa'] = JSON.stringify(user_reply);
                }
            }
            var request = new Model('account.journal').call('fetch', [[this.id], '/connect/step', this.online_type, params])
                .then(function(result){
                    var resp_json = JSON.parse(result);
                    self.parse_json_result(resp_json);
                });
        }
    },

    show_account_selector: function(resp_json) {
        var self = this;
        var data = [];
        var selected = true;
        $.each(resp_json.accounts, function(k,v){
            data = data.concat({
                name: v.meta.name,
                accountId: v._id,
                containerType: v.type,
                checked: selected,
            });
            selected = false;
        });
        this.token = resp_json.access_token
        this.configurator_wizard.$footer.find('.js_process_next_step').hide();
        this.configurator_wizard.$footer.find('.js_process_mfa_step').hide();
        this.configurator_wizard.$footer.find('.js_conclude_configuration').removeClass('hide');
        this.configurator_wizard.$el.find('.js_online_sync_form').html(QWeb.render('OnlineSynchAccountSelector', {accounts: data}));
        this.attach_datepicker();
    },

    complete_process: function(){
        //Create account on journal
        var self = this;
        if (this._super()) {
            var sync_date = this.datepicker.get_value();
            var option_selected = this.configurator_wizard.$el.find('input[name="account-selection"]:checked');
            var account_name = option_selected.attr('value');
            var account_id = option_selected.attr('account');
            var rpc = new Model('account.journal').call('save_online_account', [[this.id], {'last_sync': sync_date, 'token': this.token, 'plaid_id': account_id, 'name': account_name, 'journal_id': this.id}, this.online_institution_id])
                .then(function(result) {
                    self.configurator_wizard.close();
                    self.do_action(result);
                });
        }
    },

    fetch_site_info: function() {
        this._super();
        this.online_type = 'plaid';
        return new Model('account.journal').call('fetch', [[this.id], '/institutions/'+this.online_id, this.online_type, {}, 'get']);
    },
});

/**
 * Registry of form fields
 */
core.form_widget_registry
    .add('plaidAccountConfiguration', PlaidAccountConfigurationWidget);
});
