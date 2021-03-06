odoo.define('ups_shipping_ept.checkout', function (require) {
	
    require('web.dom_ready');
    var ajax = require('web.ajax');

    /* Handle interactive carrier choice + cart update */
    var $pay_button = $('#o_payment_form_pay');
    
    var _oncCarrierUpdateAnswer = function(result) {
    	console.log("myscript into execution")
        var $amount_delivery = $('#order_delivery span.oe_currency_value');
        var $amount_untaxed = $('#order_total_untaxed span.oe_currency_value');
        var $amount_tax = $('#order_total_taxes span.oe_currency_value');
        var $amount_total = $('#order_total span.oe_currency_value');
        var $carrier_badge = $('#delivery_carrier input[name="delivery_type"][value=' + result.carrier_id + '] ~ .badge.hidden');
        var $compute_badge = $('#delivery_carrier input[name="delivery_type"][value=' + result.carrier_id + '] ~ .o_delivery_compute');
        if (result.status === true) {
            $amount_delivery.text(result.new_amount_delivery);
            $amount_untaxed.text(result.new_amount_untaxed);
            $amount_tax.text(result.new_amount_tax);
            $amount_total.text(result.new_amount_total);
            $carrier_badge.children('span').text(result.new_amount_delivery+" ( ETA : "+result.estimated_arrival_date+" )");
            $carrier_badge.removeClass('hidden');
            $compute_badge.addClass('hidden');
            $pay_button.prop('disabled', false);
        }
        else {
            console.error(result.error_message);
            $compute_badge.text(result.error_message);
            $amount_delivery.text(result.new_amount_delivery);
            $amount_untaxed.text(result.new_amount_untaxed);
            $amount_tax.text(result.new_amount_tax);
            $amount_total.text(result.new_amount_total);
        }
    };

    var _oncCarrierClick = function(ev) {
        $pay_button.prop('disabled', true);
        var carrier_id = $(ev.currentTarget).val();
        var values = {'carrier_id': carrier_id};
        ajax.jsonRpc('/shop/update_carrier', 'call', values)
        .then(_oncCarrierUpdateAnswer);
    };

    var $carriers = $("#delivery_carrier input[name='delivery_type']");
    console.log($carriers)
    $carriers.off('click');
    $carriers.click(_oncCarrierClick);
    // Workaround to:
    // - update the amount/error on the label at first rendering
    // - prevent clicking on 'Pay Now' if the shipper rating fails
    
    if ($carriers.length > 0) {
    	$carriers.filter(':checked').off('click');
    	$carriers.filter(':checked').click();
    }

    /* Handle stuff */
    $(".oe_website_sale select[name='shipping_id']").off('change')
    $(".oe_website_sale select[name='shipping_id']").on('change', function () {
        var value = $(this).val();
        var $provider_free = $("select[name='country_id']:not(.o_provider_restricted), select[name='state_id']:not(.o_provider_restricted)");
        var $provider_restricted = $("select[name='country_id'].o_provider_restricted, select[name='state_id'].o_provider_restricted");
        if (value === 0) {
            // Ship to the same address : only show shipping countries available for billing
            $provider_free.hide().attr('disabled', true);
            $provider_restricted.show().attr('disabled', false).change();
        } else {
            // Create a new address : show all countries available for billing
            $provider_free.show().attr('disabled', false).change();
            $provider_restricted.hide().attr('disabled', true);
        }
    });

});
