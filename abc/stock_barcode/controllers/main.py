from openerp import http, _
from openerp.http import request

class StockBarcodeController(http.Controller):

    @http.route('/stock_barcode/scan_from_main_menu', type='json', auth='user')
    def main_menu(self, barcode, **kw):
        """ Receive a barcode scanned from the main menu and return the appropriate
            action (open an existing / new picking) or warning.
        """
        # Get the action to open a picking form as a dict
        action_picking_form = request.env.ref('stock_barcode.stock_picking_action_form')
        action_picking_form = action_picking_form.read()[0]

        # If the barcode represents a picking, open it
        corresponding_picking = request.env['stock.picking'].search([
            ('name', '=', barcode),
            ('state', 'in', ('partially_available', 'assigned'))
        ], limit=1)
        if corresponding_picking:
            action_picking_form['res_id'] = corresponding_picking.id
            return {'action': action_picking_form}

        # If the barcode represents a location, open a new picking from this location
        corresponding_location = request.env['stock.location'].search([
            ('barcode', '=', barcode),
            ('usage', '=', 'internal')
        ], limit=1)
        if corresponding_location:
            internal_picking_type = request.env['stock.picking.type'].search([('code', '=', 'internal')])
            warehouse = request.env['stock.location'].get_warehouse(corresponding_location)
            if warehouse:
                internal_picking_type = internal_picking_type.filtered(lambda r: r.warehouse_id.id == warehouse)
            dest_loc = corresponding_location
            while dest_loc.location_id and dest_loc.location_id.usage == 'internal':
                dest_loc = dest_loc.location_id
            if internal_picking_type:
                # Create and confirm an internal picking
                picking = request.env['stock.picking'].create({
                    'picking_type_id': internal_picking_type[0].id,
                    'location_id': corresponding_location.id,
                    'location_dest_id': dest_loc.id,
                })
                picking.action_confirm()

                # Open its form view
                action_picking_form.update(res_id=picking.id)
                return {'action': action_picking_form}
            else:
                return {'warning': _('No internal picking type. Please configure one in warehouse settings.')}

        return {'warning': _('No picking or location corresponding to barcode %(barcode)s') % {'barcode': barcode}}
