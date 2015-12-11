odoo.define('account_yodlee.acc_config_widget', function(require) {
"use strict";

var core = require('web.core');
var common = require('web.form_common');
var Model = require('web.Model');
var framework = require('web.framework');
var online_sync = require('account_online_sync.acc_config_widget');

var QWeb = core.qweb;
var _t = core._t;


var YodleeAccountConfigurationWidget = online_sync.OnlineSynchAccountConfigurationWidget.extend({

    map_field_type: function(fieldType){
        switch (fieldType){
            case 'TEXT':
                return 'text';
            case 'IF_PASSWORD':
                return 'password';
            case 'OPTIONS':
                return 'option';
            case 'CHECKBOX':
                return 'checkbox';
            case 'RADIO':
                return 'radio';
            // case 'IF_LOGIN':
            // case 'URL':
            // case 'HIDDEN':
            // case 'IMAGE_URL':
            // case 'CONTENT_URL':
            // case 'CUSTOM':
            // case 'CLUDGE':
            //     return 'text';
            case 'SECURITY_QUESTION':
                return 'security';
            case 'TOKEN_ID':
                return 'token';
            case 'IMAGE':
                return 'image';
            default:
                return 'text';
        }
    },

    _process_input: function(index, value, type) {
        var self = this;
        var vals = {}
        if (type === 'normal' || type === 'multi') {
            vals['indexResponse'] = index;
            vals['displayName'] = value.displayName;
            vals['optional'] = value.isOptional;
            self.response['credentialFields['+index+'].displayName'] = value.displayName;
            self.response['credentialFields['+index+'].name'] = value.name;
            self.response['credentialFields['+index+'].isEditable'] = value.isEditable;
            self.response['credentialFields['+index+'].isMFA'] = value.isMFA;
            self.response['credentialFields['+index+'].isOptionalMFA'] = value.isOptionalMFA;
            self.response['credentialFields['+index+'].helpText'] = value.helpText;
            if (type === 'normal') {
                vals['fieldType'] = self.map_field_type(value.fieldType.typeName);
                vals['maxlength'] = value.maxlength || -1;
                vals['selectValues'] = value.validValues;   
                vals['selectValuesDisplay'] = value.displayValidValues;
                self.response['credentialFields['+index+'].fieldType.typeName'] = value.fieldType.typeName;
                self.response['credentialFields['+index+'].size'] = value.size;
                self.response['credentialFields['+index+'].valueIdentifier'] = value.valueIdentifier;
                self.response['credentialFields['+index+'].valueMask'] = value.valueMask;
                self.response['credentialFields['+index+'].maxlength'] = value.maxlength;
                if (value.validValues !== undefined) {
                    $.each(value.validValues, function(k, v){
                        self.response['credentialFields['+index+'].validValues['+k+']'] = v;
                        self.response['credentialFields['+index+'].displayValidValues['+k+']'] = value.displayValidValues[k];
                    });
                }
            }
            else {
                var typesMulti = [];
                $.each(value.fieldTypes, function(k,v) {
                    typesMulti = typesMulti.concat({
                        fieldType: self.map_field_type(v.typeName),
                        index: k,
                        maxlength: value.maxlengths[k] || -1,
                        selectValues: value.validValues[k],
                        selectValuesDisplay: value.displayValidValues[k],
                    });
                    self.response['credentialFields['+index+'].fieldTypes['+k+'].typeName'] = v.typeName;
                    self.response['credentialFields['+index+'].sizes['+k+']'] = value.sizes[k];
                    self.response['credentialFields['+index+'].valueIdentifiers['+k+']'] = value.valueIdentifiers[k];
                    self.response['credentialFields['+index+'].valueMasks['+k+']'] = value.valueMasks[k];
                    self.response['credentialFields['+index+'].maxlengths['+k+']'] = value.maxlengths[k];
                    if (value.validValues[k] !== null) {
                        $.each(value.validValues[k], function(k2, v2){
                            self.response['credentialFields['+index+'].validValues['+k+']['+k2+']'] = v2;
                            self.response['credentialFields['+index+'].displayValidValues['+k+']['+k2+']'] = v.displayValidValues[k][k2];
                        });
                }
                });
                vals['fieldType'] = 'multi';
                vals['fieldTypeMulti'] = typesMulti;
                self.response['credentialFields['+index+'].enclosedType'] = 'com.yodlee.common.FieldInfoMultiFixed';
            }
        }
        return vals;
    },

    post_process_connection_result: function(resp_json) {
        var self = this;
        this._super();

        //process login form
        var inputs_vals = []
        this.response = {'siteId': this.view.fields.online_id.get("value"),
                         'credentialFields.enclosedType': 'com.yodlee.common.FieldInfoSingle'}
        var index = 0;
        $.each(resp_json.componentList, function(k,v) {
            if (v.isOptional == undefined) {
                v.isOptional = false;
            }
            var vals = {};
            if (v.fieldTypes != undefined) {
                vals = self._process_input(index, v, 'multi');
            }
            else if (v.fieldInfoList !== undefined) {
                var vals_tmp = [];
                $.each(v.fieldInfoList, function(k, val){
                    var args = 'normal';
                    if (val.fieldTypes !== undefined)
                        args = 'multi';
                    var result = self._process_input(index, val, args);
                    if (k < v.fieldInfoList.length-1) {
                        result['or'] = true;
                    }
                    vals_tmp = vals_tmp.concat(result);
                    vals = vals_tmp;
                    index = index + 1;
                });
            }
            else if (v.fieldType != undefined) {
                vals = self._process_input(index, v, 'normal');
            }
            index = index + 1;
            inputs_vals = inputs_vals.concat(vals);
            
        });
        this.config_template_data = {inputs: inputs_vals};
    },

    process_next_step: function() {
        var self = this;
        if (this._super()){
            self.display_wait();
            var inputs = $(".js_online_sync_input");
            _.each(inputs, function(input){
                self.response['credentialFields[' + input.id + '].value'] = input.value;
            });
            var inputs_multi = $(".js_online_sync_input_multi");
            _.each(inputs_multi, function(input){
                self.response['credentialFields[' + input.id + '].values[' + $(input).attr("subid") + ']'] = input.value;
            });
            framework.blockUI();
            var request = new Model('account.journal').call('fetch', [[this.id], '/jsonsdk/SiteAccountManagement/addSiteAccount1', this.online_type, this.response])
                .then(function(result){
                    var resp_json = JSON.parse(result);
                    //Check for error and exception first
                    if (resp_json.siteRefreshInfo === undefined || resp_json.errorOccurred === "true"){
                        self.show_error("ERROR: " + resp_json.exceptionType);
                    }
                    //Check siteRefreshStatus, should be REFRESH_TRIGGERED
                    else if (resp_json.siteRefreshInfo.siteRefreshStatus.siteRefreshStatus === 'REFRESH_TRIGGERED'){
                        //Check if MFA needed
                        self.siteAccountId = resp_json.siteAccountId;
                        if (resp_json.siteRefreshInfo.siteRefreshMode.refreshMode === 'MFA'){
                            self.get_mfa_process(resp_json.siteAccountId);
                        }
                        else {
                            self.refresh_process(resp_json.siteAccountId, 30);
                        }
                    }
                    else{
                        self.show_error("Incorrect Refresh state received", resp_json.siteRefreshInfo.siteRefreshStatus.siteRefreshStatus);
                    }

                });
        }
    },

    complete_process: function() {
        var self = this;
        if (this._super()){
            //Get back sync date information and selected account_id and create online.account object with those information
            var sync_date = this.datepicker.get_value();
            var option_selected = this.configurator_wizard.$el.find('input[name="account-selection"]:checked');
            var account_name = option_selected.attr('value');
            var account_id = option_selected.attr('account');
            var rpc = new Model('account.journal').call('save_online_account', [[this.id], {'last_sync': sync_date, 'site_account_id': this.siteAccountId, 'account_id': account_id, 'name': account_name, 'journal_id': this.id}, this.online_institution_id])
                .then(function(result) {
                    self.configurator_wizard.close();
                    self.do_action(result);
                });
        }
    },

    show_account_selector: function(resp_json) {
        framework.unblockUI();
        var self = this;
        var data = [];
        var selected = true;
        $.each(resp_json, function(k,v){
            // if (v.contentServiceInfo.containerInfo.containerName === 'credits' || v.contentServiceInfo.containerInfo.containerName === 'bank') {
                $.each(v.itemData.accounts, function(index, value){
                    data = data.concat({
                        name: value.accountName,
                        accountId: value.itemAccountId,
                        containerType: v.contentServiceInfo.containerInfo.containerName,
                        checked: selected,
                    });
                    selected = false;
                });
            // }
        });
        this.configurator_wizard.$footer.find('.js_process_next_step').hide();
        this.configurator_wizard.$footer.find('.js_process_mfa_step').hide();
        this.configurator_wizard.$footer.find('.js_conclude_configuration').toggleClass('hide');
        this.configurator_wizard.$el.find('.js_online_sync_form').html(QWeb.render('OnlineSynchAccountSelector', {accounts: data}));
        this.configurator_wizard.$el.find('.js_online_sync_form').show();
        this.configurator_wizard.$el.find('.js_online_sync_wait').hide();
        this.attach_datepicker();
    },

    refresh_process: function(siteAccountId, number) {
        //Call getSiteRefreshInfo
        var self = this;
        var params = {memSiteAccId: siteAccountId};
        if (number === 0) {
            // framework.unblockUI();
            self.show_error("Request Time Out");
        }
        else {
            var request = new Model('account.journal').call('fetch', [[this.id], '/jsonsdk/Refresh/getSiteRefreshInfo', this.online_type, params])
                .then(function(result){
                    var resp_json = JSON.parse(result);
                    var refresh_status = resp_json.siteRefreshStatus.siteRefreshStatus;
                    if (resp_json.code === undefined || resp_json.errorOccurred === "true"){
                        self.show_error("ERROR: " + resp_json.exceptionType);
                    }
                    if (resp_json.code === 801 || (resp_json.code === 0 && refresh_status !== 'REFRESH_COMPLETED' && refresh_status !== 'REFRESH_COMPLETED_ACCOUNTS_ALREADY_AGGREGATED')) {
                        if (refresh_status === 'REFRESH_TIMED_OUT'){
                            number = 1;
                        }
                        setTimeout(function(){self.refresh_process(siteAccountId, number-1)}, 2000);
                    }
                    else{
                        if (resp_json.code === 0) {
                            var get_account_request = new Model('account.journal').call('fetch', [[self.id], '/jsonsdk/DataService/getItemSummariesForSite', self.online_type, params])
                                .then(function(result){
                                    //Show selection of account and online sync date for user to choose
                                    self.show_account_selector(JSON.parse(result));
                                });
                        }
                        else {
                            //ERROR
                            // framework.unblockUI();
                            self.show_error(self.map_error_code(resp_json.code));
                        }   
                    }
            })
        }
    },

    get_mfa_process: function(siteAccountId) {
        var self = this;
        //Call getMFAResponseForSite to check if we have some MFA to complete
        var request = new Model('account.journal').call('fetch', [[this.id], '/jsonsdk/Refresh/getMFAResponseForSite', this.online_type, {memSiteAccId: siteAccountId}])
            .then(function(result){
                var resp_json = JSON.parse(result);
                if (resp_json.errorOccurred === 'true') {
                    self.show_error("ERROR: "+resp_json.detailedMessage);
                }
                if (resp_json.errorCode === undefined) {
                    if (resp_json.isMessageAvailable === true) {
                        //Present MFA to user
                        
                        self.show_mfa_to_user(resp_json, siteAccountId);
                    }
                    else {
                        self.get_mfa_process(siteAccountId);
                    }
                }
                else {
                    // framework.unblockUI();
                    if (resp_json.errorCode === 0) {
                        // framework.blockUI();
                        self.refresh_process(siteAccountId, 30);
                    }
                    else {
                        //ERROR
                        self.show_error(self.map_error_code(resp_json.errorCode));
                    }
                }
            });
    },

    show_mfa_to_user: function(resp_json, siteAccountId) {
        framework.unblockUI();
        var self = this;
        var v = resp_json.fieldInfo;
        // $.each(resp_json.fieldInfo, function(k, v){

        var qaquestions = [];
        self.qaResponse = {'memSiteAccId': siteAccountId};
        if (v.questionAndAnswerValues !== undefined){
            $.each(v.questionAndAnswerValues, function(k,value){
                if (value.isRequired === "true") {
                    qaquestions = qaquestions.concat({name: value.question, indexResponse: k});
                    self.qaResponse["userResponse.quesAnsDetailArray["+k+"].answerFieldType"] = value.responseFieldType;
                    self.qaResponse["userResponse.quesAnsDetailArray["+k+"].metaData"] = value.metaData;
                    self.qaResponse["userResponse.quesAnsDetailArray["+k+"].question"] = value.question;
                    self.qaResponse["userResponse.quesAnsDetailArray["+k+"].questionFieldType"] = value.questionFieldType;
                }
            });
        }

        var qdict = {name: v.displayString,
            fieldType: this.map_field_type(v.mfaFieldInfoType),
            image: v.image && btoa(String.fromCharCode.apply(null, new Uint8Array(v.image))),
            maxlength: v.maximumLength,
            questions: qaquestions,
        };
        // });
        this.configurator_wizard.$footer.find('.js_process_next_step').hide();
        this.configurator_wizard.$footer.find('.js_process_mfa_step').removeClass('hide');
        this.configurator_wizard.$el.find('.js_online_sync_form').html(QWeb.render('YodleeMFAResponse', {question: qdict}));
        this.configurator_wizard.$el.find('.js_online_sync_form').show();
        this.configurator_wizard.$el.find('.js_online_sync_wait').addClass('hide');
    },

    process_mfa_step: function() {
        var self = this;
        if (this._super()){
            self.display_wait();
            if ($('.js_yodlee_captcha').length > 0){
                self.qaResponse['userResponse.objectInstanceType'] = 'com.yodlee.core.mfarefresh.MFAImageResponse';
                self.qaResponse['userResponse.imageString'] = $('.js_yodlee_captcha').val();
            }
            if ($('.js_yodlee_security').length > 0){
                self.qaResponse['userResponse.objectInstanceType'] = 'com.yodlee.core.mfarefresh.MFAQuesAnsResponse';
                $.each($('.js_yodlee_security'), function(k, value){
                    self.qaResponse['userResponse.quesAnsDetailArray['+value.id+'].answer'] = value.value;
                })
            }
            if ($('.js_yodlee_token').length > 0){
                self.qaResponse['userResponse.objectInstanceType'] = 'com.yodlee.core.mfarefresh.MFATokenResponse';
                self.qaResponse['userResponse.token'] = $('.js_yodlee_token').val();
            }
            var sent_request = new Model('account.journal').call('fetch', [[this.id], '/jsonsdk/Refresh/putMFARequestForSite', this.online_type, self.qaResponse])
                .then(function(result){
                    var resp_json = JSON.parse(result);
                    if (resp_json.primitiveObj === true) {
                        framework.blockUI();
                        self.get_mfa_process(self.siteAccountId);
                    }
                    else {
                        if (resp_json.errorOccurred === "true"){
                            self.show_error("ERROR: "+resp_json.detailedMessage);
                        }
                        else {
                            self.show_error("Error Occured, please close wizard and retry");
                        }
                    }
                });
        }
    },

    fetch_site_info: function() {
        this._super();
        this.online_type = 'yodlee';
        var param = {'siteId': this.online_id};
        return new Model('account.journal').call('fetch', [[this.id], '/jsonsdk/SiteAccountManagement/getSiteLoginForm', this.online_type, param]);
    },

    display_wait: function() {
        this.configurator_wizard.$footer.find('.js_process_next_step').addClass('hide');
        this.configurator_wizard.$footer.find('.js_process_mfa_step').addClass('hide');
        this.configurator_wizard.$footer.find('.js_conclude_configuration').addClass('hide');
        this.configurator_wizard.$el.find('.js_online_sync_form').hide();
        this.configurator_wizard.$el.find('.js_online_sync_wait').removeClass('hide');
    },

    map_error_code: function(errorCode) {
        switch (errorCode) {
            case 409:
                return "Problem Updating Account(409): We could not update your account because the end site is experiencing technical difficulties.";
            case 411:
                return "Site No Longer Available (411):The site no longer provides online services to its customers.  Please delete this account.";
            case 412:
                return "Problem Updating Account(412): We could not update your account because the site is experiencing technical difficulties.";
            case 415:
                return "Problem Updating Account(415): We could not update your account because the site is experiencing technical difficulties.";
            case 416:
                return "Multiple User Logins(416): We attempted to update your account, but another session was already established at the same time.  If you are currently logged on to this account directly, please log off and try after some time";
            case 418:
                return "Problem Updating Account(418): We could not update your account because the site is experiencing technical difficulties. Please try later.";
            case 423:
                return "No Account Found (423): We were unable to detect an account. Please verify that you account information is available at this time and If the problem persists, please contact customer support at online@odoo.com for further assistance.";
            case 424:
                return "Site Down for Maintenance(424):We were unable to update your account as the site is temporarily down for maintenance. We apologize for the inconvenience.  This problem is typically resolved in a few hours. Please try later.";
            case 425:
                return "Problem Updating Account(425): We could not update your account because the site is experiencing technical difficulties. Please try later.";
            case 426:
                return "Problem Updating Account(426): We could not update your account for technical reasons. This type of error is usually resolved in a few days. We apologize for the inconvenience.";
            case 505:
                return "Site Not Supported (505): We currently does not support the security system used by this site. We apologize for any inconvenience. Check back periodically if this situation has changed.";
            case 510:
                return "Property Record Not Found (510): The site is unable to find any property information for your address. Please verify if the property address you have provided is correct.";
            case 511:
                return "Home Value Not Found (511): The site is unable to provide home value for your property. We suggest you to delete this site.";
            case 402:
                return "Credential Re-Verification Required (402): We could not update your account because your username and/or password were reported to be incorrect.  Please re-verify your username and password.";
            case 405:
                return "Update Request Canceled(405):Your account was not updated because you canceled the request.";
            case 406:
                return "Problem Updating Account (406): We could not update your account because the site requires you to perform some additional action. Please visit the site or contact its customer support to resolve this issue. Once done, please update your account credentials in case they are changed else try again.";
            case 407:
                return "Account Locked (407): We could not update your account because it appears your account has been locked. This usually results from too many unsuccessful login attempts in a short period of time. Please visit the site or contact its customer support to resolve this issue.  Once done, please update your account credentials in case they are changed.";
            case 414:
                return "Requested Account Type Not Found (414): We could not find your requested account. You may have selected a similar site under a different category by accident in which case you should select the correct site.";
            case 417:
                return "Account Type Not Supported(417):The type of account we found is not currently supported.  Please remove this site and add as a  manual account.";
            case 420:
                return "Credential Re-Verification Required (420):The site has merged with another. Please re-verify your credentials at the site and update the same.";
            case 421:
                return "Invalid Language Setting (421): The language setting for your site account is not English. Please visit the site and change the language setting to English.";
            case 422:
                return "Account Reported Closed (422): We were unable to update your account information because it appears one or more of your related accounts have been closed.  Please deactivate or delete the relevant account and try again.";
            case 427:
                return "Re-verification Required (427): We could not update your account due to the site requiring you to view a new promotion. Please log in to the site and click through to your account overview page to update the account.  We apologize for the inconvenience.";
            case 428:
                return "Re-verification Required (428): We could not update your account due to the site requiring you to accept a new Terms & Conditions. Please log in to the site and read and accept the T&C.";
            case 429:
                return "Re-Verification Required (429): We could not update your account due to the site requiring you to verify your personal information. Please log in to the site and update the fields required.";
            case 430:
                return "Site No Longer Supported (430):This site is no longer supported for data updates. Please deactivate or delete your account. We apologize for the inconvenience.";
            case 433:
                return "Registration Requires Attention (433): Auto registration is not complete. Please complete your registration at the end site. Once completed, please complete adding this account.";
            case 434:
                return "Registration Requires Attention (434): Your Auto-Registration could not be completed and requires further input from you.  Please re-verify your registration information to complete the process.";
            case 435:
                return "Registration Requires Attention (435): Your Auto-Registration could not be completed and requires further input from you.  Please re-verify your registration information to complete the process.";
            case 436:
                return "Account Already Registered (436):Your Auto-Registration could not be completed because the site reports that your account is already registered.  Please log in to the site to confirm and then complete the site addition process with the correct login information.";
            case 506:
                return "New Login Information Required(506):We're sorry, to log in to this site, you need to provide additional information. Please update your account and try again.";
            case 512:
                return "No Payees Found(512):Your request cannot be completed as no payees were found in your account.";
            case 518:
                return "MFA error: Authentication Information Unavailable (518):Your account was not updated as the required additional authentication information was unavailable. Please try now.";
            case 519:
                return "MFA error: Authentication Information Required (519): Your account was not updated as your authentication information like security question and answer was unavailable or incomplete. Please update your account settings.";
            case 520:
                return "MFA error: Authentication Information Incorrect (520):We're sorry, the site indicates that the additional authentication information you provided is incorrect. Please try updating your account again.";
            case 521:
                return "MFA error: Additional Authentication Enrollment Required (521) : Please enroll in the new security authentication system, <Account Name> has introduced. Ensure your account settings in <Cobrand> are updated with this information.";
            case 522:
                return "MFA error: Request Timed Out (522) :Your request has timed out as the required security information was unavailable or was not provided within the expected time. Please try again.";
            case 523:
                return "MFA error: Authentication Information Incorrect (523):We're sorry, the authentication information you  provided is incorrect. Please try again.";
            case 524:
                return "MFA error: Authentication Information Expired (524):We're sorry, the authentication information you provided has expired. Please try again.";
            case 526:
                return "MFA error: Credential Re-Verification Required (526): We could not update your account because your username/password or additional security credentials are incorrect. Please try again.";
            case 401:
                return "Problem Updating Account(401):We're sorry, your request timed out. Please try again.";
            case 403:
                return "Problem Updating Account(403):We're sorry, there was a technical problem updating your account. This kind of error is usually resolved in a few days. Please try again later.";
            case 404:
                return "Problem Updating Account(404):We're sorry, there was a technical problem updating your account. Please try again later.";
            case 408:
                return "Account Not Found(408): We're sorry, we couldn't find any accounts for you at the site. Please log in at the site and confirm that your account is set up, then try again.";
            case 413:
                return "Problem Updating Account(413):We're sorry, we couldn't update your account at the site because of a technical issue. This type of problem is usually resolved in a few days. Please try again later.";
            case 419:
                return "Problem Updating Account(419):We're sorry, we couldn't update your account because of unexpected variations at the site. This kind of problem is usually resolved in a few days. Please try again later.";
            case 507:
                return "Problem Updating Account(507):We're sorry, Yodlee has just started providing data updates for this site, and it may take a few days to be successful as we get started. Please try again later.";
            case 508:
                return "Request Timed Out (508): We are sorry, your request timed out due to technical reasons. Please try again.";
            case 509:
                return "MFA error: Site Device Information Expired(509): We're sorry, we can't update your account because your token is no longer valid at the site. Please update your information and try again, or contact customer support.";
            case 517:
                return "Problem Updating Account (517) :We'resorry, there was a technical problem updating your account. Please try again.";
            case 525:
                return "MFA error: Problem Updating Account (525): We could not update your account for technical reasons. This type of error is usually resolved in a few days. We apologize for the inconvenience. Please try again later.";
            default:
                return "An Error has Occurred ("+errorCode+"). Please contact support at online@odoo.com"
        }
    },

});

core.form_widget_registry.add('yodleeAccountConfiguration', YodleeAccountConfigurationWidget);
    
});
