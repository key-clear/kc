# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from datetime import datetime, date
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.http import request


def _build_sql_query(fields, tables, conditions, query_args):

    # The conditions should use named arguments and these arguments are in query_args.

    if query_args.get('contract_ids'):
        tables.append("account_analytic_account")
        tables.append("sale_subscription")
        conditions.append("account_invoice_line.account_analytic_id = account_analytic_account.id")
        conditions.append("sale_subscription.template_id IN %(contract_ids)s")
        conditions.append("sale_subscription.analytic_account_id = account_analytic_account.id")

    fields_str = ', '.join(fields)
    tables_str = ', '.join(tables)
    conditions_str = ' AND '.join(conditions)

    base_query = "SELECT %s FROM %s WHERE %s" % (fields_str, tables_str, conditions_str)

    request.cr.execute(base_query, query_args)
    return request.cr.dictfetchall()


def compute_net_revenue(start_date, end_date, contract_ids=None):
    fields = ['SUM(account_invoice_line.price_subtotal_signed)']
    tables = ['account_invoice_line', 'account_invoice']
    conditions = [
        "account_invoice.date_invoice BETWEEN %(start_date)s AND %(end_date)s",
        "account_invoice_line.invoice_id = account_invoice.id",
        "account_invoice.type IN ('out_invoice', 'out_refund')",
        "account_invoice.state NOT IN ('draft', 'cancel')",
    ]

    sql_results = _build_sql_query(fields, tables, conditions, {
        'start_date': start_date,
        'end_date': end_date,
        'contract_ids': tuple(contract_ids or []),
    })

    return 0 if not sql_results or not sql_results[0]['sum'] else int(sql_results[0]['sum'])


def compute_arpu(start_date, end_date, contract_ids=None):
    mrr = compute_mrr(start_date, end_date, contract_ids=contract_ids)
    nb_customers = compute_nb_contracts(start_date, end_date, contract_ids=contract_ids)
    result = 0 if not nb_customers else mrr/float(nb_customers)
    return int(result)


def compute_arr(start_date, end_date, contract_ids=None):
    result = 12*compute_mrr(start_date, end_date, contract_ids=contract_ids)
    return int(result)


def compute_ltv(start_date, end_date, contract_ids=None):
    # LTV = Average Monthly Recurring Revenue Per Customer / User Churn Rate
    mrr = compute_mrr(start_date, end_date, contract_ids=contract_ids)
    nb_contracts = compute_nb_contracts(start_date, end_date, contract_ids=contract_ids)
    avg_mrr_per_customer = 0 if nb_contracts == 0 else mrr / float(nb_contracts)
    logo_churn = compute_logo_churn(start_date, end_date, contract_ids=contract_ids)
    result = 0 if logo_churn == 0 else avg_mrr_per_customer/float(logo_churn)
    return int(result)


def compute_nrr(start_date, end_date, contract_ids=None):

    fields = ['SUM(account_invoice_line.price_subtotal_signed)']
    tables = ['account_invoice_line', 'account_invoice']
    conditions = [
        "(account_invoice.date_invoice BETWEEN %(start_date)s AND %(end_date)s)",
        "account_invoice_line.invoice_id = account_invoice.id",
        "account_invoice.type IN ('out_invoice', 'out_refund')",
        "account_invoice.state NOT IN ('draft', 'cancel')",
        "account_invoice_line.asset_start_date IS NULL",
    ]

    sql_results = _build_sql_query(fields, tables, conditions, {
        'start_date': start_date,
        'end_date': end_date,
        'contract_ids': tuple(contract_ids or []),
    })

    return 0 if not sql_results or not sql_results[0]['sum'] else int(sql_results[0]['sum'])


def compute_nb_contracts(start_date, end_date, contract_ids=None):
    fields = ['COUNT(DISTINCT account_invoice_line.account_analytic_id) AS sum']
    tables = ['account_invoice_line', 'account_invoice']
    conditions = [
        "date %(date)s BETWEEN account_invoice_line.asset_start_date AND account_invoice_line.asset_end_date",
        "account_invoice.id = account_invoice_line.invoice_id",
        "account_invoice.type IN ('out_invoice', 'out_refund')",
        "account_invoice.state NOT IN ('draft', 'cancel')",
        "account_invoice_line.account_analytic_id IS NOT NULL"
    ]

    sql_results = _build_sql_query(fields, tables, conditions, {
        'date': end_date,
        'contract_ids': tuple(contract_ids or []),
    })

    return 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']


def compute_mrr(start_date, end_date, contract_ids=None):
    fields = ['SUM(account_invoice_line.asset_mrr)']
    tables = ['account_invoice_line', 'account_invoice']
    conditions = [
        "date %(date)s BETWEEN account_invoice_line.asset_start_date AND account_invoice_line.asset_end_date",
        "account_invoice.id = account_invoice_line.invoice_id",
        "account_invoice.type IN ('out_invoice', 'out_refund')",
        "account_invoice.state NOT IN ('draft', 'cancel')"
    ]

    sql_results = _build_sql_query(fields, tables, conditions, {
        'date': end_date,
        'contract_ids': tuple(contract_ids or []),
    })

    return 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']


def compute_logo_churn(start_date, end_date, contract_ids=None):

    fields = ['COUNT(DISTINCT account_invoice_line.account_analytic_id) AS sum']
    tables = ['account_invoice_line', 'account_invoice']
    conditions = [
        "date %(date)s - interval '1 months' BETWEEN account_invoice_line.asset_start_date AND account_invoice_line.asset_end_date",
        "account_invoice.id = account_invoice_line.invoice_id",
        "account_invoice.type IN ('out_invoice', 'out_refund')",
        "account_invoice.state NOT IN ('draft', 'cancel')",
        "account_invoice_line.account_analytic_id IS NOT NULL"
    ]

    sql_results = _build_sql_query(fields, tables, conditions, {
        'date': end_date,
        'contract_ids': tuple(contract_ids or []),
    })

    active_customers_1_month_ago = 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']

    fields = ['COUNT(DISTINCT account_invoice_line.account_analytic_id) AS sum']
    tables = ['account_invoice_line', 'account_invoice']
    conditions = [
        "date %(date)s - interval '1 months' BETWEEN account_invoice_line.asset_start_date AND account_invoice_line.asset_end_date",
        "account_invoice.id = account_invoice_line.invoice_id",
        "account_invoice.type IN ('out_invoice', 'out_refund')",
        "account_invoice.state NOT IN ('draft', 'cancel')",
        "account_invoice_line.account_analytic_id IS NOT NULL",
        """NOT exists (
                    SELECT 1 from account_invoice_line ail
                    WHERE ail.account_analytic_id = account_invoice_line.account_analytic_id
                    AND (date %(date)s BETWEEN ail.asset_start_date AND ail.asset_end_date)
                )
        """,
    ]

    sql_results = _build_sql_query(fields, tables, conditions, {
        'date': end_date,
        'contract_ids': tuple(contract_ids or []),
    })

    resigned_customers = 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']

    return 0 if not active_customers_1_month_ago else resigned_customers/float(active_customers_1_month_ago)


def compute_revenue_churn(start_date, end_date, contract_ids=None):

    fields = ['SUM(account_invoice_line.asset_mrr) AS sum']
    tables = ['account_invoice_line', 'account_invoice']
    conditions = [
        "date %(date)s - interval '1 months' BETWEEN account_invoice_line.asset_start_date AND account_invoice_line.asset_end_date",
        "account_invoice.id = account_invoice_line.invoice_id",
        "account_invoice.type IN ('out_invoice', 'out_refund')",
        "account_invoice.state NOT IN ('draft', 'cancel')",
        "account_invoice_line.account_analytic_id IS NOT NULL",
        """NOT exists (
                    SELECT 1 from account_invoice_line ail
                    WHERE ail.account_analytic_id = account_invoice_line.account_analytic_id
                    AND (date %(date)s BETWEEN ail.asset_start_date AND ail.asset_end_date)
                )
        """
    ]

    sql_results = _build_sql_query(fields, tables, conditions, {
        'date': end_date,
        'contract_ids': tuple(contract_ids or []),
    })

    churned_mrr = 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']
    previous_month_mrr = compute_mrr(start_date, (end_date - relativedelta(months=+1)), contract_ids=contract_ids)
    return 0 if previous_month_mrr == 0 else (churned_mrr)/float(previous_month_mrr)


def compute_mrr_growth_values(start_date, end_date, contract_ids=None):
    new_mrr = 0
    expansion_mrr = 0
    down_mrr = 0
    churned_mrr = 0
    net_new_mrr = 0

    # 1. NEW
    fields = ['SUM(account_invoice_line.asset_mrr) AS sum']
    tables = ['account_invoice_line', 'account_invoice']
    conditions = [
        "date %(date)s BETWEEN account_invoice_line.asset_start_date AND account_invoice_line.asset_end_date",
        "account_invoice.id = account_invoice_line.invoice_id",
        "account_invoice.type IN ('out_invoice', 'out_refund')",
        "account_invoice.state NOT IN ('draft', 'cancel')",
        "account_invoice_line.account_analytic_id IS NOT NULL",
        """NOT exists (
                    SELECT 1 from account_invoice_line ail
                    WHERE ail.account_analytic_id = account_invoice_line.account_analytic_id
                    AND (date %(date)s - interval '1 months' BETWEEN ail.asset_start_date AND ail.asset_end_date)
                )
        """
    ]

    sql_results = _build_sql_query(fields, tables, conditions, {
        'date': end_date,
        'contract_ids': tuple(contract_ids or []),
    })

    new_mrr = 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']

    # 2. DOWN & EXPANSION - TODO: remove SQL query and use_build_sql_query instead
    if not contract_ids:
        request.cr.execute("""
            SELECT old_line.account_analytic_id, old_line.sum AS old_sum, new_line.sum AS new_sum, (new_line.sum - old_line.sum) AS diff
            FROM (
                SELECT account_analytic_id, SUM(asset_mrr) AS sum
                FROM account_invoice_line AS line, account_invoice AS invoice
                WHERE asset_start_date BETWEEN date %(date)s - interval '1 months' + interval '1 days' and date %(date)s AND
                    invoice.id = line.invoice_id AND
                    invoice.type IN ('out_invoice', 'out_refund') AND
                    invoice.state NOT IN ('draft', 'cancel')
                GROUP BY account_analytic_id
                ) AS new_line,
                (
                SELECT account_analytic_id, SUM(asset_mrr) AS sum
                FROM account_invoice_line AS line, account_invoice AS invoice
                WHERE asset_end_date BETWEEN date %(date)s - interval '2 months' + interval '1 days' and date %(date)s AND
                    invoice.id = line.invoice_id AND
                    invoice.type IN ('out_invoice', 'out_refund') AND
                    invoice.state NOT IN ('draft', 'cancel')
                GROUP BY account_analytic_id
                ) AS old_line
            WHERE
                new_line.account_analytic_id IS NOT NULL AND
                old_line.account_analytic_id = new_line.account_analytic_id
        """, {
            'date': end_date,
        })
    else:
        request.cr.execute("""
            SELECT old_line.account_analytic_id, old_line.sum AS old_sum, new_line.sum AS new_sum, (new_line.sum - old_line.sum) AS diff
            FROM (
                SELECT account_analytic_id, SUM(asset_mrr) AS sum
                FROM account_invoice_line AS line, account_invoice AS invoice, account_analytic_account AS analytic_account, sale_subscription as contract
                WHERE asset_start_date BETWEEN date %(date)s - interval '1 months' + interval '1 days' and date %(date)s AND
                    invoice.id = line.invoice_id AND
                    invoice.type IN ('out_invoice', 'out_refund') AND
                    invoice.state NOT IN ('draft', 'cancel') AND
                    line.account_analytic_id = analytic_account.id AND
                    contract.template_id IN %(contracts)s AND
                    contract.analytic_account_id = analytic_account.id
                GROUP BY account_analytic_id
                ) AS new_line,
                (
                SELECT account_analytic_id, SUM(asset_mrr) AS sum
                FROM account_invoice_line AS line, account_invoice AS invoice, account_analytic_account AS analytic_account, sale_subscription as contract
                WHERE asset_end_date BETWEEN date %(date)s - interval '2 months' + interval '1 days' and date %(date)s AND
                    invoice.id = line.invoice_id AND
                    invoice.type IN ('out_invoice', 'out_refund') AND
                    invoice.state NOT IN ('draft', 'cancel') AND
                    line.account_analytic_id = analytic_account.id AND
                    contract.template_id IN %(contracts)s AND
                    contract.analytic_account_id = analytic_account.id
                GROUP BY account_analytic_id
                ) AS old_line
            WHERE
                new_line.account_analytic_id IS NOT NULL AND
                old_line.account_analytic_id = new_line.account_analytic_id
        """, {
            'date': end_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'contracts': tuple(contract_ids)
        })
    sql_results = request.cr.dictfetchall()
    for account in sql_results:
        if account['diff'] > 0:
            expansion_mrr += account['diff']
        else:
            down_mrr -= account['diff']

    # 3. CHURNED
    fields = ['SUM(account_invoice_line.asset_mrr)']
    tables = ['account_invoice_line', 'account_invoice']
    conditions = [
        "date %(date)s - interval '1 months' BETWEEN account_invoice_line.asset_start_date AND account_invoice_line.asset_end_date",
        "account_invoice.id = account_invoice_line.invoice_id",
        "account_invoice.type IN ('out_invoice', 'out_refund')",
        "account_invoice.state NOT IN ('draft', 'cancel')",
        "account_invoice_line.account_analytic_id IS NOT NULL",
        """NOT exists (
                    SELECT 1 from account_invoice_line ail
                    WHERE ail.account_analytic_id = account_invoice_line.account_analytic_id
                    AND (date %(date)s BETWEEN ail.asset_start_date AND ail.asset_end_date)
                )
        """,
    ]

    sql_results = _build_sql_query(fields, tables, conditions, {
        'date': end_date,
        'contract_ids': tuple(contract_ids or []),
    })

    churned_mrr = 0 if not sql_results or not sql_results[0]['sum'] else sql_results[0]['sum']

    net_new_mrr = new_mrr - churned_mrr + expansion_mrr - down_mrr

    return {
        'new_mrr': new_mrr,
        'churned_mrr': -churned_mrr,
        'expansion_mrr': expansion_mrr,
        'down_mrr': -down_mrr,
        'net_new_mrr': net_new_mrr,
    }


STAT_TYPES = {
    'mrr': {
        'name': 'Monthly Recurring Revenue',
        'code': 'mrr',
        'dir': 'up',
        'prior': 1,
        'type': 'last',
        'add_symbol': 'currency',
        'compute': compute_mrr
    },
    'net_revenue': {
        'name': 'Net Revenue',
        'code': 'net_revenue',
        'dir': 'up',
        'prior': 2,
        'type': 'sum',
        'add_symbol': 'currency',
        'compute': compute_net_revenue
    },
    'nrr': {
        'name': 'Non-Recurring Revenue',
        'code': 'nrr',
        'dir': 'up',  # 'down' if fees ?
        'prior': 3,
        'type': 'sum',
        'add_symbol': 'currency',
        'compute': compute_nrr
    },
    'arpu': {
        'name': 'Revenue per Contract',
        'code': 'arpu',
        'dir': 'up',
        'prior': 4,
        'type': 'last',
        'add_symbol': 'currency',
        'compute': compute_arpu
    },
    'arr': {
        'name': 'Annual Run-Rate',
        'code': 'arr',
        'dir': 'up',
        'prior': 5,
        'type': 'last',
        'add_symbol': 'currency',
        'compute': compute_arr
    },
    'ltv': {
        'name': 'Lifetime Value',
        'code': 'ltv',
        'dir': 'up',
        'prior': 6,
        'type': 'last',
        'add_symbol': 'currency',
        'compute': compute_ltv
    },
    'logo_churn': {
        'name': 'Logo Churn',
        'code': 'logo_churn',
        'dir': 'down',
        'prior': 7,
        'type': 'last',
        'add_symbol': '%',
        'compute': compute_logo_churn
    },
    'revenue_churn': {
        'name': 'Revenue Churn',
        'code': 'revenue_churn',
        'dir': 'down',
        'prior': 8,
        'type': 'last',
        'add_symbol': '%',
        'compute': compute_revenue_churn
    },
    'nb_contracts': {
        'name': 'Contracts',
        'code': 'nb_contracts',
        'dir': 'up',
        'prior': 9,
        'type': 'last',
        'add_symbol': '',
        'compute': compute_nb_contracts
    },
}

FORECAST_STAT_TYPES = {
    'mrr_forecast': {
        'name': 'Forecasted Annual MRR Growth',
        'code': 'mrr_forecast',
        'prior': 1,
        'add_symbol': 'currency',
    },
    'contracts_forecast': {
        'name': 'Forecasted Annual Contracts Growth',
        'code': 'contracts_forecast',
        'prior': 2,
        'add_symbol': '',
    },
}
