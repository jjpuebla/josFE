app_name = "josfe"
app_title = "Facturación Electrónica JOS"
app_publisher = "JP"
app_description = "Facturación electrónica Joselo "
app_email = "jjpuebla@hotmail.com"
app_license = "mit"

fixtures = [
    {
        "dt": "Client Script",
        "filters": [
            ["name", "in", [
                "JOS_Tax_Id_Validador", 
                "Address-City-Sync",
                "Customer - Sync Nombre Cliente"
            ]]
        ]
    },
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", [
                "Customer-custom_tab_9",
                "Customer-custom_jos_tax_id_validador", 
                "Customer-custom_jos_city2",
                "Customer-custom_jos_direccion",
                "Customer-custom_jos_country",
                "Customer-custom_jos_nombre_cliente",
                "Customer-custom_jos_emails",
                "Customer-custom_jos_telefonos",
                "Address-custom_jos_ecua_cities"
            ]]
        ]
    },
    {
        "dt": "Property Setter",
        "filters": [
            ["doc_type", "in", [
                "Customer", "Address"
            ]],
            ["name", "in", [
                "Address-country-default",
                "Customer-customer_type-allow_in_quick_entry",
                "Customer-salutation-depends_on",
                "Customer-salutation-hidden",
                "Customer-customer_type-read_only",
                "Customer-main-quick_entry",
            ]]
        ]
    }
]




# Server Scripts
doc_events = {
    "Customer": {
        "validate": "josfe.custom.Customer.Tax_Id_Validador.validate_tax_id",
        "after_insert": "josfe.custom.Customer.Create_Quick_Customer.create_linked_address"
    }
}



# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "josfe",
# 		"logo": "/assets/josfe/logo.png",
# 		"title": "Facturación Electrónica JOS",
# 		"route": "/josfe",
# 		"has_permission": "josfe.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/josfe/css/josfe.css"
# app_include_js = "/assets/josfe/js/josfe.js"

# include js, css files in header of web template
# web_include_css = "/assets/josfe/css/josfe.css"
# web_include_js = "/assets/josfe/js/josfe.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "josfe/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "josfe/public/icons.svg"

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
# 	"methods": "josfe.utils.jinja_methods",
# 	"filters": "josfe.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "josfe.install.before_install"
# after_install = "josfe.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "josfe.uninstall.before_uninstall"
# after_uninstall = "josfe.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "josfe.utils.before_app_install"
# after_app_install = "josfe.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "josfe.utils.before_app_uninstall"
# after_app_uninstall = "josfe.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "josfe.notifications.get_notification_config"

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

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"josfe.tasks.all"
# 	],
# 	"daily": [
# 		"josfe.tasks.daily"
# 	],
# 	"hourly": [
# 		"josfe.tasks.hourly"
# 	],
# 	"weekly": [
# 		"josfe.tasks.weekly"
# 	],
# 	"monthly": [
# 		"josfe.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "josfe.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "josfe.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "josfe.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["josfe.utils.before_request"]
# after_request = ["josfe.utils.after_request"]

# Job Events
# ----------
# before_job = ["josfe.utils.before_job"]
# after_job = ["josfe.utils.after_job"]

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
# 	"josfe.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

