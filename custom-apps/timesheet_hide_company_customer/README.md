# Timesheet Hide Company Customer

This small Frappe app hides the standard `Company` and `Customer` fields on
`Timesheet` forms. The fields remain in the DocType and can still be populated
by defaults, server scripts, imports, or integrations.

Install the app on the target bench, add it to the site, then run:

`bench --site <site> migrate && bench --site <site> clear-cache && bench build`

Reload the browser with Ctrl+Shift+R. Merely copying this folder into the
Docker host does not load the hook; the app must be installed with
`bench --site <site> install-app timesheet_hide_company_customer`.
