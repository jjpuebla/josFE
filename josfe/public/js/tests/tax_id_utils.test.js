(async function () {
  const res = await fetch('/assets/josfe/taxidvalidator/testdata/tax_ids.json');
  const cases = await res.json();

  const v = (window.__josfe_tax && window.__josfe_tax.validators) || {};
  const validateNaturalPerson = v.validateNaturalPerson;
  const validatePublicRUC = v.validatePublicRUC;
  const validatePrivateRUC = v.validatePrivateRUC;

  function isValidJS(id) {
    if (id.startsWith("P-")) return true;
    if (id === "9999999999999") return true;
    const third = id[2];
    if (third === "9" && validatePrivateRUC) return validatePrivateRUC(id);
    if (third === "6" && validatePublicRUC)  return validatePublicRUC(id);
    if (validateNaturalPerson) return validateNaturalPerson(id);
    return false;
  }

  let pass = 0, fail = 0;
  for (const c of cases) {
    const ok = isValidJS(c.id) === c.valid;
    if (ok) pass++; else fail++;
  }

  console.log(`JOSFE tax_id_utils.js tests: pass=${pass} fail=${fail}`);
  if (fail > 0) {
    alert(`❌ tax_id_utils.js tests failing: ${fail} cases`);
  } else {
    alert("✅ tax_id_utils.js tests passed");
  }
})();