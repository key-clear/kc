echo "Creating 'www' bundle for cordova app"

./generate_extension.sh

[ -d www ] || mkdir www
cp -r extension/static www
cp extension/timesheet.html www/index.html

cp -r www /home/odoo/phonegap/OdooTimesheets/
cp www/static/src/img/icon.png /home/odoo/phonegap/OdooTimesheets/

cd /home/odoo/phonegap/OdooTimesheets/
cordova prepare android
