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

function registerClickListenerForAvatar() {
    function addContainerEventListeners(el) {
        el.addEventListener('click', function (event) {
            console.log("avatar container clicked");
            avatarFileInput.click();
        });

        el.addEventListener('dragover', function (event) {
            console.log("drag over");
            event.preventDefault();
            avatarContainer.classList.add('drag-over');
        });

        el.addEventListener('dragleave', function () {
            avatarContainer.classList.remove('drag-over');
        });

        el.addEventListener('drop', function (event) {
            console.log("image dropped");
            event.preventDefault();
            avatarContainer.classList.remove('drag-over');
            const file = event.dataTransfer.files[0];
            if (file) {
                previewImage(file);
                updateFileInput(file); // Assign the dropped file to the file input
            }
        });
    }

    let avatarContainer = document.querySelector("img.editable-avatar, svg.editable-avatar");
    const avatarFileInput = document.getElementById("avatar-img");
    addContainerEventListeners(avatarContainer);

    avatarFileInput.addEventListener('change', function (event) {
        handleFileUpload(event.target.files[0]);
        previewImage(event.target.files[0]);
    });

    // Handle the file (either from drag-drop or file input)
    function handleFileUpload(file) {
        const reader = new FileReader();
        reader.onload = function (event) {
            // Preview the image
            avatarContainer.src = event.target.result;
        }
        reader.readAsDataURL(file);
    }

    function previewImage(file) {
        const reader = new FileReader();
        reader.onload = function (event) {
            // Check if the avatarContainer is an <img> or <svg>
            console.log("avatar container: ", avatarContainer.tagName.toLowerCase());
            const result = event.target.result;  // Data URL of the selected image
            if (avatarContainer.tagName.toLowerCase() === 'svg') {
                // Create a new <img> element to replace the <svg>
                const imgElement = document.createElement('img');
                imgElement.classList.add('avatar')
                imgElement.classList.add('editable-avatar');  // Add the same class
                imgElement.src = result;  // Set the data URL as the src
                imgElement.width = 110;
                imgElement.height = 110;

                // Replace the <svg> with the new <img>
                avatarContainer.parentNode.replaceChild(imgElement, avatarContainer);

                // Update avatarContainer to reference the new img element and add event listeners
                avatarContainer = imgElement;
                addContainerEventListeners(avatarContainer);
            } else {
                // If it's already an <img>, just update the src
                avatarContainer.src = result;
            }
        };
        reader.readAsDataURL(file);  // Read file as data URL for preview
    }

    function updateFileInput(file) {
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        avatarFileInput.files = dataTransfer.files; // Set the new file list to the input
    }
}


/**
 * @module badge-editor
 * @description
 * A custom element for editing a list of badges.
 * @property {string} input-field-id=null The id of the hidden input field that will store the badge data
 * @property {bool} white=false Whether to use the white version of the delete icon
 * @property {string} ul-class='' A class name that will be added to the badge list ul
 * @property {string} li-class='' A class name that will be added to each badge list item
 * @property {string} span-class='' A class name that will be added to each badge name span
 */
class BadgeEditor extends HTMLElement {
    constructor() {
        super();
        this.render = () => {
            const badges = this.badges;
            this.innerHTML = `
                <ul class="cluster cluster-list">
                    <!-- Badges will be inserted here -->
                    <li>
                        <input type="text" placeholder="Add badge">
                        <button type="button">Add</button>
                    </li>        
                </ul>
            `;
            const newBadgeInput = this.querySelector('input');
            const badgesList = this.querySelector('ul');
            if (this.ulClass) badgesList.classList.add(this.ulClass);
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

    get white() {
        return this.hasAttribute('white');
    }

    set white(val) {
        if (val) {
            this.setAttribute('white', '');
        } else {
            this.removeAttribute('white');
        }
    }

    get ulClass() {
        return this.getAttribute('ul-class') || '';
    }

    set ulClass(val) {
        return this.setAttribute('ul-class', val);
    }

    get liClass() {
        return this.getAttribute('li-class') || '';
    }

    set liClass(val) {
        return this.setAttribute('li-class', val);
    }

    get spanClass() {
        return this.getAttribute('span-class') || '';
    }

    set spanClass(val) {
        return this.setAttribute('span-class', val);
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
        li.className = 'badge';
        if (this.liClass) li.classList.add(this.liClass);
        const span = document.createElement('span');
        span.className = 'badge-name';
        if (this.spanClass) span.classList.add(this.spanClass);
        span.textContent = badge;
        const delButton = document.createElement('button');
        delButton.className = 'badge-delete-button';
        if (this.white) {
            delButton.classList.add('badge-delete-button:white');
        }
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
