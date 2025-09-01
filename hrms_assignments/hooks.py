app_name = "hrms_assignments"
app_title = "HRMS Assignments Submission"
app_publisher = "Sparsh Verma"
app_description = (
    "This application is a submission to the HRMS assignment given from GirmanTech"
)
app_email = "sparshv70@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "hrms_assignments",
# 		"logo": "/assets/hrms_assignments/logo.png",
# 		"title": "HRMS Assignments Submission",
# 		"route": "/hrms_assignments",
# 		"has_permission": "hrms_assignments.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/hrms_assignments/css/hrms_assignments.css"
# app_include_js = "/assets/hrms_assignments/js/hrms_assignments.js"

# include js, css files in header of web template
# web_include_css = "/assets/hrms_assignments/css/hrms_assignments.css"
# web_include_js = "/assets/hrms_assignments/js/hrms_assignments.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "hrms_assignments/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Job Applicant": "custom_script/job_applicant/job_applicant.js",
    "Employee": "custom_script/employee/employee.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "hrms_assignments/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "hrms_assignments.utils.jinja_methods",
# 	"filters": "hrms_assignments.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "hrms_assignments.install.before_install"
# after_install = "hrms_assignments.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "hrms_assignments.uninstall.before_uninstall"
# after_uninstall = "hrms_assignments.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "hrms_assignments.utils.before_app_install"
# after_app_install = "hrms_assignments.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "hrms_assignments.utils.before_app_uninstall"
# after_app_uninstall = "hrms_assignments.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hrms_assignments.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Job Applicant": {
        "validate": "hrms_assignments.custom_script.job_applicant.job_applicant.validate_job_applicant"
    },
    "Employee": {
        "before_insert": "hrms_assignments.custom_script.employee.employee.before_insert",
        "validate": "hrms_assignments.custom_script.employee.employee.validate_probation_guards",
    },
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"hrms_assignments.tasks.all"
# 	],
# 	"daily": [
# 		"hrms_assignments.tasks.daily"
# 	],
# 	"hourly": [
# 		"hrms_assignments.tasks.hourly"
# 	],
# 	"weekly": [
# 		"hrms_assignments.tasks.weekly"
# 	],
# 	"monthly": [
# 		"hrms_assignments.tasks.monthly"
# 	],
# }

scheduler_events = {
    "daily": ["hrms_assignments.scheduled.employee.run_daily_probation_reminders"]
}

# Testing
# -------

# before_tests = "hrms_assignments.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hrms_assignments.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "hrms_assignments.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["hrms_assignments.utils.before_request"]
# after_request = ["hrms_assignments.utils.after_request"]

# Job Events
# ----------
# before_job = ["hrms_assignments.utils.before_job"]
# after_job = ["hrms_assignments.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"hrms_assignments.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
