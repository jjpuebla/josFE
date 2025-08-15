// josfe/public/js/customer_hook_test.js

///////////////////////////////////////////
/// UNCOMMENT TO TEST CUSTOMER DOCTYPE  ///
///////////////////////////////////////////
console.log("Loading Customer Hook JS for testingrrrrrrrrrrrrrrrr");
frappe.ui.form.on('Customer', {
  refresh(frm) {
    console.log('✅ Customer hook loaded from josfe/public/js/customer_hook_test.js for:', frm.docname);
    // A quick visual proof without popups
    frm.dashboard.clear_headline();
    frm.dashboard.set_headline(__('Hook OK: JS loaded from josfe ✅'));
  },
  validate(frm) {
    console.log('🧪 validate() fired for:', frm.docname);
  }
});
