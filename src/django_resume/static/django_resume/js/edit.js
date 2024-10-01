/*
If then submit button is clicked, then collect all the data from the contenteditable elements
and copy them to the hidden input fields in the form. Then submit the form using htmx.
 */

function registerClickListenerForHiddenForm(pluginId, submitId, formId, initialId = null) {
    document.getElementById(submitId).addEventListener("click", function (e) {
        const pluginElement = document.getElementById(pluginId);
        const formElement = document.getElementById(formId);
        const editableElements = pluginElement.querySelectorAll("[contenteditable=true]");
        const formValues = {};
        if (initialId != null) {
            formValues["id"] = initialId;
        }
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

/* Editing badges */

let addBadgeButtonHandler = null;
let badgesListClickHandler = null;

function initBadgesForm(
    badgesListId,
    newBadgeInputId,
    addBadgeButtonId,
    hiddenBadgeListId,
    badgeNameClassName,
    badgeLiClassName,
    deleteClassName,
    submitButtonId,
    white = false
) {
    const badgesList = document.getElementById(badgesListId);
    const newBadgeInput = document.getElementById(newBadgeInputId);
    const addBadgeButton = document.getElementById(addBadgeButtonId);
    const hiddenBadgeList = document.getElementById(hiddenBadgeListId);
    const submitButton = document.getElementById(submitButtonId);

    // If the elements are not found, do not proceed
    if (
        !badgesList ||
        !newBadgeInput ||
        !addBadgeButton ||
        !hiddenBadgeList ||
        !submitButton
    ) {
        return;
    }

    // Remove existing event listeners to prevent duplication
    if (addBadgeButtonHandler) {
        addBadgeButton.removeEventListener('click', addBadgeButtonHandler);
    }
    if (badgesListClickHandler) {
        badgesList.removeEventListener('click', badgesListClickHandler);
    }

    // Function to update the hidden badge list
    function updateHiddenBadgeList() {
        const badgeNames = Array.from(
            badgesList.querySelectorAll(`.${badgeNameClassName}`)
        ).map((el) => el.textContent.trim());
        hiddenBadgeList.textContent = badgeNames.join(', ');
    }

    // Define the event handler functions

    // Handler for adding a new badge
    addBadgeButtonHandler = function (e) {
        e.preventDefault();
        const badge = newBadgeInput.value.trim();
        if (badge) {
            const existingBadges = Array.from(
                badgesList.querySelectorAll(`.${badgeNameClassName}`)
            ).map((el) => el.textContent.trim());
            if (existingBadges.includes(badge)) {
                alert('Badge already exists.');
            } else {
                const li = document.createElement('li');
                li.className = `${badgeLiClassName} badge`;
                const span = document.createElement('span');
                span.className = `${badgeNameClassName} badge-name`;
                span.textContent = badge;
                const delButton = document.createElement('button');
                delButton.className = `${deleteClassName} badge-delete-button`;
                if (white) {
                    delButton.classList.add('badge-delete-button:white');
                }
                delButton.type = 'button'; // Prevents form submission

                // Create the SVG icon
                const svgNS = 'http://www.w3.org/2000/svg';
                const svg = document.createElementNS(svgNS, 'svg');
                svg.classList.add('edit-icon-small');

                const use = document.createElementNS(svgNS, 'use');
                use.setAttributeNS('http://www.w3.org/1999/xlink', 'href', '#delete');

                svg.appendChild(use);
                delButton.appendChild(svg);

                li.appendChild(span);
                li.appendChild(delButton);
                badgesList.insertBefore(li, badgesList.lastElementChild);
                newBadgeInput.value = '';
                updateHiddenBadgeList();
            }
        }
    };


    // Handler for deleting a badge
    badgesListClickHandler = function (e) {
        const deleteButton = e.target.closest(`.${deleteClassName}`);
        if (deleteButton) {
            e.preventDefault();
            const li = deleteButton.closest('li');
            if (li && badgesList.contains(li)) {
                badgesList.removeChild(li);
                updateHiddenBadgeList();
            }
        }
    };

    // Add event listeners
    addBadgeButton.addEventListener('click', addBadgeButtonHandler);
    badgesList.addEventListener('click', badgesListClickHandler);

    // Update hidden badge list on initialization
    updateHiddenBadgeList();
}


/**
 * @module badge-editor
 * @description
 * A custom element for editing a list of badges.
 * @property {string} input-field-id=null The id of the hidden input field that will store the badge data
 */
class BadgeEditor extends HTMLElement {
    constructor() {
        super();
        this.render = () => {
            const badges = this.badges;
            this.innerHTML = `
                <ul class="cluster cluster-list skills-list">
                    <!-- Badges will be inserted here -->
                    <li>
                        <input type="text" id="new-skill-input" placeholder="Add badge">
                        <button type="button">Add</button>
                    </li>        
                </ul>
            `;
            const newBadgeInput = this.querySelector('input');
            const badgesList = this.querySelector('ul');
            const hiddenBadgesList = document.getElementById(this.inputFieldId);

            // add event listener to add badge button
            this.addBadgeButtonHandler = (e) => {
                e.preventDefault();
                const badge = newBadgeInput.value.trim();
                if (badge) {
                    const existingBadges = Array.from(badgesList.querySelectorAll('.badge-name'))
                        .map(el => el.textContent.trim());
                    if (existingBadges.includes(badge)) {
                        alert('Badge already exists.');
                    } else {
                        const li = this.getBadgeLi(badge);
                        badgesList.insertBefore(li, badgesList.lastElementChild);
                        newBadgeInput.value = '';
                        this.updateHiddenBadgesList(badgesList, hiddenBadgesList);
                    }
                }
            };
            const addBadgeButton = this.querySelector('button');
            addBadgeButton.addEventListener('click', this.addBadgeButtonHandler);

            // Delete badge handler
            this.badgesListClickHandler = (e) => {
                const deleteButton = e.target.closest('.badge-delete-button');
                if (deleteButton) {
                    e.preventDefault();
                    const li = deleteButton.closest('li');
                    if (li && badgesList.contains(li)) {
                        badgesList.removeChild(li);
                        this.updateHiddenBadgesList(badgesList, hiddenBadgesList);
                    }
                }
            };
            badgesList.addEventListener('click', this.badgesListClickHandler);

            if (badges.length > 0) {
                this.renderBadgesList(badges);
            }
        }
    }
    updateHiddenBadgesList(badgesList, hiddenBadgesList) {
        const badgeNames = Array.from(badgesList.querySelectorAll('.badge-name'))
            .map(el => el.textContent.trim());

        // console.log("update hidden badges list: ", badgeNames);
        hiddenBadgesList.value = JSON.stringify(badgeNames);
    };


    get inputFieldId() {
        return this.getAttribute('input-field-id') || null;
    }

    set inputFieldId(val) {
        return this.setAttribute('input-field-id', val);
    }

    get badges() {
        if (this.inputFieldId) {
            return JSON.parse(document.getElementById(this.inputFieldId).value);
        } else {
            return [];
        }
    }

    getBadgeLi(badge) {
        const li = document.createElement('li');
        li.className = 'skill-badge badge';
        const span = document.createElement('span');
        span.className = 'badge-name';
        span.textContent = badge;
        const delButton = document.createElement('button');
        delButton.className = 'badge-delete-button badge-delete-button:white';
        delButton.type = 'button'; // Prevents form submission
        delButton.setAttribute('aria-label', `Delete ${badge}`);  // Add aria-label needed for testing

        // Create the SVG icon
        const svgNS = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(svgNS, 'svg');
        svg.classList.add('edit-icon-small');

        const use = document.createElementNS(svgNS, 'use');
        use.setAttributeNS('http://www.w3.org/1999/xlink', 'href', '#delete');

        svg.appendChild(use);
        delButton.appendChild(svg);

        li.appendChild(span);
        li.appendChild(delButton);
        return li;
    }

    renderBadgesList(badges) {
        const badgesUl = this.getElementsByTagName('ul')[0];
        badges.forEach((badge) => {
            const li = this.getBadgeLi(badge);
            badgesUl.insertBefore(li, badgesUl.lastElementChild);
        });
    }

    connectedCallback() {
        this.render();
    }

    attributeChangedCallback() {
        this.render();
    }

    static get observedAttributes() {
        return ['input-field-id'];
    }
}

if ('customElements' in window) {
    customElements.define('badge-editor', BadgeEditor);
}
