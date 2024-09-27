/*
If then submit button is clicked, then collect all the data from the contenteditable elements
and copy them to the hidden input fields in the form. Then submit the form using htmx.
 */

function registerClickListenerForHiddenForm(pluginId, submitId, formId) {
    console.log("registerClickListenerForHiddenForm: ", pluginId, submitId, formId);
    document.getElementById(submitId).addEventListener("click", function (e) {
        const pluginElement = document.getElementById(pluginId);
        const formElement = document.getElementById(formId);
        const editableElements = pluginElement.querySelectorAll("[contenteditable=true]");
        const formValues = {};
        editableElements.forEach((field) => {
            const fieldName = field.dataset.field;
            const fieldValue = field.textContent.trim();
            formValues[fieldName] = fieldValue;
            const hiddenInput = formElement.querySelector(`input[type="hidden"][data-field="${fieldName}"]`);
            if (hiddenInput) {
                hiddenInput.value = fieldValue;
            }
        });
        htmx.trigger(formElement, "submit");
    });
}
