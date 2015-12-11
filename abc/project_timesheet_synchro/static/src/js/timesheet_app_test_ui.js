odoo.define('project_timesheet_synchro.test_screen_navigation', function (require) {
'use strict';

var Tour = require('web.Tour');

Tour.register({
    id:   'activity_creation',
    name: "Record an activity",
    path: '/project_timesheet_synchro/timesheet_app',
    mode: 'test',
    steps: [
    	{
            title:     "Wait for it",
            waitFor:   '.pt_toggle',
        },
        {
            title:     "Open the menu",
            element:   '.pt_toggle',
            waitFor: ".pt_drawer_menu_wrapper"
        },
        {
            title:     "Close the menu",
            element:   '.pt_drawer_menu_wrapper',
            waitFor: '.pt_btn_start_timer',
        },
        {
            title:     "Wait a bit",
            wait:   '100',
        },
        {
            title:     "Start the timer",
            element:   '.pt_btn_start_timer',
        },
        {
            title:     "Stop the timer",
            element:   '.pt_btn_stop_timer',
        },
        {
            title:     "Wait a bit",
            wait:   '100',
        },
        {
            title:     "Open the project selection",
            element:   '.pt_activity_project .select2-choice',
        },
        {
        	title: "Enter a project name",
        	element : '.select2-input',
        	sampleText: "A project Name",
        },
		{
        	title: "Create the project",
        	element : '.select2-result-label:contains("A project Name")',
        },
        {
            title:     "Wait a bit",
            wait:   '400',
        },
        {
            title:     "Save the activity",
            element:   '.pt_validate_edit_btn',
        },
        {
            title:     "Wait a bit",
            wait:   '100',
        },
    ]
});

Tour.register({
    id:   'test_screen_navigation',
    name: "Test screen navigation",
    path: '/project_timesheet_synchro/timesheet_app',
    mode: 'test',
    steps: [
    	{
            title:     "Wait for it",
            waitFor:   '.pt_toggle',
        },
        {
        	title:     "Open the menu",
            element:   '.pt_toggle',
            waitFor: ".pt_drawer_menu_wrapper"
        },
        {
        	title: '"Go to screen This week"',
        	element: '.pt_menu_item:contains("This Week")',
        	wait: 100,
        },
        {
        	title:     "Open the menu",
            element:   '.pt_toggle',
            waitFor: ".pt_drawer_menu_wrapper"
        },
        {
        	title: '"Go to screen Settings"',
        	element: '.pt_menu_item:contains("Settings")',
        	wait: 100,
        },
        {
        	title:     "Open the menu",
            element:   '.pt_toggle',
            waitFor: ".pt_drawer_menu_wrapper"
        },
        {
        	title: '"Go to screen Day Plan"',
        	element: '.pt_menu_item:contains("Plan")',
        	wait: 100,
        },
        {
        	title:     "Open the menu",
            element:   '.pt_toggle',
            waitFor: ".pt_drawer_menu_wrapper",
        },
        {
        	title: '"Go to screen Synchronize"',
        	element: '.pt_menu_item:contains("Synchronize")',
        	wait: 100,
        },
        {
        	title:     "Open the menu",
            element:   '.pt_toggle',
            waitFor: ".pt_drawer_menu_wrapper",
        },
        {
        	title: '"Go to screen Statistics"',
        	element: '.pt_menu_item:contains("Statistics")',
        	wait: 100,
        },
        {
        	title:     "Open the menu",
            element:   '.pt_toggle',
            waitFor: ".pt_drawer_menu_wrapper"
        },
    ]
});


});