odoo.define('website_contract.website_contract', function (require) {
    'use strict';

    var website = require('website.website');
    var ajax = require('web.ajax');
    if(!$('.oe_website_contract').length) {
        return $.Deferred().reject("DOM doesn't contain '.js_surveyresult'");
    }

    $('.contract-submit').off('click').on('click', function () {
        $(this).attr('disabled', true);
        $(this).prepend('<i class="fa fa-refresh fa-spin"></i> ');
        $(this).closest('form').submit();
    });

    var $new_payment_method = $('#new_payment_method');
    $('#wc-payment-form select[name="pay_meth"]').change(function() {
        var $form = $(this).parents('form');
        var has_val = parseInt($(this).val()) !== -1;
        $new_payment_method.toggleClass('hidden', has_val);
        $form.find('button').toggleClass('hidden', !has_val);
    });

    // When creating new pay method: create by json-rpc then continue with the new id in the form
    $new_payment_method.on("click", 'button[type="submit"],button[name="submit"]', function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      $(this).attr('disabled', true);
      $(this).prepend('<i class="fa fa-refresh fa-spin"></i> ');
      var $form = $(ev.currentTarget).parents('form');
      var $main_form = $('#wc-payment-form');
      var action = $form.attr('action');
      var data = getFormData($form);
      ajax.jsonRpc(action, 'call', data).then(function (data) {
        $main_form.find('select option[value="-1"]').val(data[0]);
        $main_form.find('select').val(data[0]);
        $main_form.submit();
      });
    });

    function getFormData($form){
        var unindexed_array = $form.serializeArray();
        var indexed_array = {};

        $.map(unindexed_array, function(n, i){
            indexed_array[n['name']] = n['value'];
        });

        return indexed_array;
    };

});