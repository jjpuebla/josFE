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
            ["module", "in", ["ClienteSetup", "my_data", "compras", "sri_invoicing"]]
        ]
    },

    {
        "dt": "Custom Field",
        "filters": [
            ["module", "in", ["ClienteSetup", "my_data", "compras", "sri_invoicing"]]
        ]
    },

    {
        "dt": "Property Setter",
        "filters": [
            ["module", "in", ["ClienteSetup", "my_data", "compras", "sri_invoicing"]]
        ]
    },
    {
        "dt": "DocType",
        "filters": [
            ["module", "in", ["ClienteSetup", "my_data", "compras", "sri_invoicing"]]
        ]
    },
    {
        "dt": "DocField",
        "filters": [
            ["parent", "=", "Contact Phone"],
        ]
    }
]

# Server Scripts
import josfe.api.contact_hooks

doc_events = {
    "Contact": {
        "on_update": "josfe.api.contact_hooks.refresh_html",
        "validate": "josfe.api.phone_validator.validate_contact_phones"
    },
    "Customer": {
        "validate": [
            "josfe.clientesetup.validadores_customer.validate_tax_id",
            "josfe.api.phone_validator.validate_entity_phones",
            "josfe.taxidvalidator.ec_tax_validator.enforce_tax_id_immutability"
        ],
        "on_update": "josfe.api.create_quick_entity.sync_customer_supplier",
        "after_insert": "josfe.api.create_quick_entity.sync_customer_supplier",
        "autoname": "josfe.overrides.customer_naming.autoname_customer"
    },
    "Supplier": {
        "validate": [
            "josfe.compras.validadores_supplier.validate_tax_id",
            "josfe.api.phone_validator.validate_entity_phones",
            "josfe.taxidvalidator.ec_tax_validator.enforce_tax_id_immutability"
        ],
        "on_update": "josfe.api.create_quick_entity.sync_customer_supplier",
        "after_insert": "josfe.api.create_quick_entity.sync_customer_supplier",
        "autoname": "josfe.overrides.supplier_naming.autoname_supplier"

    },
    "Company": {
        "validate": [
            "josfe.my_data.validadores_company.validate_tax_id",
            "josfe.taxidvalidator.ec_tax_validator.enforce_tax_id_immutability",
            "josfe.my_data.validadores_company.sync_company_name"
        ],
    },
    "Warehouse": {
        "validate": [
            "josfe.sri_invoicing.validations.warehouse.validate_warehouse_sri",
            "josfe.sri_invoicing.validations.warehouse.validate_no_duplicate_pe_per_parent",
    ],
    },
    "Sales Invoice": {        
        "autoname": "josfe.sri_invoicing.numbering.serie_autoname.si_autoname",
        "before_save": "josfe.sri_invoicing.numbering.serie_autoname.si_before_save",
        "before_submit": "josfe.sri_invoicing.numbering.hooks_sales_invoice.si_before_submit",
        "on_submit": "josfe.sri_invoicing.queue.api.enqueue_on_sales_invoice_submit",
        "on_cancel": "josfe.sri_invoicing.queue.api.on_sales_invoice_cancel",
    },
    "SRI Puntos Emision": {
        "on_trash": "josfe.sri_invoicing.warehouse_guards.prevent_deleting_emission_point"
    },

    
}

# js files:
app_include_js = "/assets/josfe/js/loader.js"

app_include_css = [
    "/assets/josfe/css/sri_seq.css",             
]

# Map Doctype -> JS file (path is relative to your app's package root)
doctype_js = {
    "Warehouse": "public/js/warehouse_sri_seq.min.js",
    "Sales Invoice": "public/js/sales_invoice_series.js",
    "Credenciales SRI": "public/js/sri_credential.js",
}

scheduler_events = {
    "daily": [
        "josfe.sri_invoicing.numbering.validate.daily_check",
    ]
}

boot_session = "josfe.user_location.session.extend_boot_with_location"

permission_query_conditions = {
  "Sales Invoice": "josfe.user_location.permissions.get_permission_query_conditions"
}
has_permission = {
  "Sales Invoice": "josfe.user_location.permissions.has_permission"
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

