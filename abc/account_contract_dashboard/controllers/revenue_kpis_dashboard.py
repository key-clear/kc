# -*- coding: utf-8 -*-
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from datetime import datetime, date, timedelta
from math import floor
from openerp import http
from openerp.http import request
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from stat_types import STAT_TYPES, FORECAST_STAT_TYPES, compute_mrr_growth_values


class RevenueKPIsDashboard(http.Controller):

    @http.route('/account_contract_dashboard/fetch_data', type='json', auth='user')
    def fetch_data(self):

        return {
            'stat_types': {stat: {k: STAT_TYPES[stat][k] for k in ('name', 'dir', 'code', 'prior', 'add_symbol')} for stat in STAT_TYPES},
            'forecast_stat_types': FORECAST_STAT_TYPES,
            'currency_symbol': request.env.user.company_id.currency_id.symbol,
            'currency_id': request.env.user.company_id.currency_id.id,
            'show_demo': request.env['account.invoice.line'].search_count([('asset_start_date', '!=', False)]) == 0,
        }

    @http.route('/account_contract_dashboard/get_default_values_forecast', type='json', auth='user')
    def get_default_values_forecast(self, forecast_type, end_date=None):

        if not end_date:
            end_date = date.today()
        else:
            end_date = datetime.strptime(end_date, DEFAULT_SERVER_DATE_FORMAT)

        net_new_mrr = compute_mrr_growth_values(end_date, end_date)['net_new_mrr']
        revenue_churn = self.compute_stat('revenue_churn', end_date, end_date)

        result = {
            'expon_growth': 15,
            'churn': revenue_churn,
            'projection_time': 12,
        }

        if 'mrr' in forecast_type:
            mrr = self.compute_stat('mrr', end_date, end_date)

            result['starting_value'] = mrr
            result['linear_growth'] = net_new_mrr
        else:
            arpu = self.compute_stat('arpu', end_date, end_date)
            nb_contracts = self.compute_stat('nb_contracts', end_date, end_date)

            result['starting_value'] = nb_contracts
            result['linear_growth'] = 0 if arpu == 0 else net_new_mrr/arpu
        return result

    @http.route('/account_contract_dashboard/get_stats_history', type='json', auth='user')
    def get_stats_history(self, stat_type, start_date, end_date, contract_ids=None):

        start_date = datetime.strptime(start_date, DEFAULT_SERVER_DATE_FORMAT)
        end_date = datetime.strptime(end_date, DEFAULT_SERVER_DATE_FORMAT)

        results = {}

        for delta in [1, 3, 12]:
            results['value_' + str(delta) + '_months_ago'] = self.compute_stat(
                stat_type,
                start_date - relativedelta(months=+delta),
                end_date - relativedelta(months=+delta),
                contract_ids=contract_ids)

        return results

    @http.route('/account_contract_dashboard/get_stats_by_plan', type='json', auth='user')
    def get_stats_by_plan(self, stat_type, start_date, end_date, contract_ids=None):

        results = []

        domain = [('type', '=', 'template')]
        if contract_ids:
            domain += [('id', 'in', contract_ids)]

        contract_ids = request.env['sale.subscription'].search(domain)

        for contract in contract_ids:
            sale_subscriptions = request.env['sale.subscription'].search([('template_id', '=', contract.id)])
            analytic_account_ids = [sub.analytic_account_id.id for sub in sale_subscriptions]
            recurring_invoice_line_ids = request.env['account.invoice.line'].search([
                ('asset_start_date', '<=', end_date),
                ('asset_end_date', '>=', end_date),
                ('account_analytic_id', 'in', analytic_account_ids),
            ])
            value = self.compute_stat(stat_type, start_date, end_date, contract_ids=[contract.id])
            results.append({
                'name': contract.name,
                'nb_customers': len(recurring_invoice_line_ids.mapped('account_analytic_id')),
                'value': value,
            })

        results = sorted((results), key=lambda k: k['value'], reverse=True)

        return results

    @http.route('/account_contract_dashboard/compute_graph_stat', type='json', auth='user')
    def compute_graph_stat(self, stat_type, start_date, end_date, contract_ids=None, points_limit=30):

        start_date = datetime.strptime(start_date, DEFAULT_SERVER_DATE_FORMAT)
        end_date = datetime.strptime(end_date, DEFAULT_SERVER_DATE_FORMAT)
        delta = end_date - start_date

        ticks = self._get_pruned_tick_values(range(delta.days + 1), points_limit)

        results = []

        for i in ticks:
            # METHOD NON-OPTIMIZED (could optimize it using SQL with generate_series)
            date = start_date + timedelta(days=i)
            value = self.compute_stat(stat_type, date, date, contract_ids=contract_ids)

            # '0' and '1' are the keys for nvd3 to render the graph
            results.append({
                '0': str(date).split(' ')[0],
                '1': value,
            })

        return results

    @http.route('/account_contract_dashboard/compute_graph_mrr_growth', type='json', auth='user')
    def compute_graph_mrr_growth(self, start_date, end_date, contract_ids=None, points_limit=0):

        # By default, points_limit = 0 mean every points

        start_date = datetime.strptime(start_date, DEFAULT_SERVER_DATE_FORMAT)
        end_date = datetime.strptime(end_date, DEFAULT_SERVER_DATE_FORMAT)
        delta = end_date - start_date

        ticks = self._get_pruned_tick_values(range(delta.days + 1), points_limit)

        results = defaultdict(list)

        # This is rolling month calculation
        for i in ticks:
            date = start_date + timedelta(days=i)
            date_splitted = str(date).split(' ')[0]

            computed_values = compute_mrr_growth_values(date, date, contract_ids=contract_ids)

            for k in ['new_mrr', 'churned_mrr', 'expansion_mrr', 'down_mrr', 'net_new_mrr']:
                results[k].append({
                    '0': date_splitted,
                    '1': computed_values[k]
                })

        return results

    @http.route('/account_contract_dashboard/compute_stat_trend', type='json', auth='user')
    def compute_stat_trend(self, stat_type, start_date, end_date, contract_ids=None):

        start_date = datetime.strptime(start_date, DEFAULT_SERVER_DATE_FORMAT)
        end_date = datetime.strptime(end_date, DEFAULT_SERVER_DATE_FORMAT)
        start_date_delta = start_date - relativedelta(months=+1)
        end_date_delta = end_date - relativedelta(months=+1)

        value_1 = self.compute_stat(stat_type, start_date_delta, end_date_delta, contract_ids=contract_ids)
        value_2 = self.compute_stat(stat_type, start_date, end_date, contract_ids=contract_ids)

        perc = 0 if value_1 == 0 else round(100*(value_2 - value_1)/float(value_1), 1)

        result = {
            'value_1': str(value_1),
            'value_2': str(value_2),
            'perc': perc,
        }
        return result

    @http.route('/account_contract_dashboard/compute_stat', type='json', auth='user')
    def compute_stat(self, stat_type, start_date, end_date, contract_ids=None):

        if isinstance(start_date, (str, unicode)):
            start_date = datetime.strptime(start_date, DEFAULT_SERVER_DATE_FORMAT)
        if isinstance(end_date, (str, unicode)):
            end_date = datetime.strptime(end_date, DEFAULT_SERVER_DATE_FORMAT)

        return STAT_TYPES[stat_type]['compute'](start_date, end_date, contract_ids=contract_ids)

    def _get_pruned_tick_values(self, ticks, nb_desired_ticks):
        if nb_desired_ticks == 0:
            return ticks

        nb_values = len(ticks)
        keep_one_of = max(1, floor(nb_values / float(nb_desired_ticks)))

        ticks = [x for x in ticks if x % keep_one_of == 0]

        return ticks
