# -*- coding: utf-8 -*-
import models

# This method is used to load the institution of yodlee upon installation (post_init_hook)
def _load_csv(cr, registry):
    import os
    import csv
    from openerp.tools import misc
    pathname = os.path.join('account_yodlee', 'data', 'online.institution.csv')
    vals = []
    with misc.file_open(pathname) as f:
        for row in csv.reader(f, delimiter=';', quotechar='"'):
            vals.append(tuple(row))

    if vals:
        cr.executemany("""INSERT INTO online_institution(online_id, name, type) VALUES (%s,%s,%s)""", vals)