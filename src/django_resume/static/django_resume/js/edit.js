class EditableForm extends HTMLElement {
    constructor() {
        super();
    }

    connectedCallback() {
        // Access elements within the component
        const formElement = this.querySelector('form');
        const submitButton = this.querySelector('button[type="submit"]');
        const contentEditableElements = this.querySelectorAll('[contenteditable="true"]');
        const checkbox = this.querySelector('input[type="checkbox"]');

        // Handle checkbox separately since it's a special case
        if (checkbox) {
            checkbox.addEventListener('change', (e) => {
                const hiddenInput = formElement.querySelector(`input[type="hidden"][data-field="${checkbox.dataset.field}"]`);
                if (hiddenInput) {
                    // Use "on" when checked, which is what Django expects from checkbox inputs
                    hiddenInput.value = checkbox.checked ? "on" : "";
                }
            });
        }

        submitButton.addEventListener('click', (e) => {
            e.preventDefault(); // Prevent the default form submission

            // Collect data from contenteditable elements
            contentEditableElements.forEach((field) => {
                const fieldName = field.dataset.field;
                const fieldType = field.dataset.type;
                let fieldValue;

                if (fieldType === "html") {
                    fieldValue = field.innerHTML.trim();
                } else {
                    fieldValue = field.textContent.trim();
                }

                // Update the corresponding hidden input field
                const hiddenInput = formElement.querySelector(`input[type="hidden"][data-field="${fieldName}"]`);
                if (hiddenInput) {
                    hiddenInput.value = fieldValue;
                }
            });

            // Submit the form using htmx
            htmx.trigger(formElement, 'submit');
        });

        // Handle file inputs and their preview elements
        const fileInputs = this.querySelectorAll('input[type="file"]');

        fileInputs.forEach((fileInput) => {
            this.setupFileInput(fileInput);
        });
    }

    setupFileInput(fileInput) {
        const fieldName = fileInput.name;
        let previewElements = Array.from(this.querySelectorAll(`.editable-avatar[data-field="${fieldName}"]`));

        const addEventListenersToPreviewElement = (previewElement) => {
            previewElement.addEventListener('click', () => {
                fileInput.click();
            });

            previewElement.addEventListener('dragover', (event) => {
                event.preventDefault();
                previewElement.classList.add('drag-over');
            });

            previewElement.addEventListener('dragleave', () => {
                previewElement.classList.remove('drag-over');
            });

            previewElement.addEventListener('drop', (event) => {
                event.preventDefault();
                previewElement.classList.remove('drag-over');
                const file = event.dataTransfer.files[0];
                if (file) {
                    handleFileUpload(file);
                    updateFileInput(file);
                }
            });
        };

        const handleFileUpload = (file) => {
            const reader = new FileReader();
            reader.onload = (event) => {
                const result = event.target.result;

                previewElements.forEach((previewElement) => {
                    if (previewElement.tagName.toLowerCase() === 'svg') {
                        const imgElement = document.createElement('img');
                        imgElement.classList = previewElement.classList;
                        imgElement.dataset.field = previewElement.dataset.field;
                        imgElement.src = result;

                        if (previewElement.hasAttribute('width')) {
                            imgElement.setAttribute('width', previewElement.getAttribute('width'));
                        }
                        if (previewElement.hasAttribute('height')) {
                            imgElement.setAttribute('height', previewElement.getAttribute('height'));
                        }

                        previewElement.parentNode.replaceChild(imgElement, previewElement);

                        const index = previewElements.indexOf(previewElement);
                        previewElements[index] = imgElement;

                        addEventListenersToPreviewElement(imgElement);
                    } else {
                        previewElement.src = result;
                    }
                });
            };
            reader.readAsDataURL(file);
        };

        const updateFileInput = (file) => {
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);

            try {
                fileInput.files = dataTransfer.files;
            } catch (error) {
                // Handle the error during tests or in environments where assignment fails
                // Optionally, log the error or ignore it
            }
        }

        previewElements.forEach((previewElement) => {
            addEventListenersToPreviewElement(previewElement);
        });

        fileInput.addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (file) {
                handleFileUpload(file);
            }
        });
    }
}

// Define the custom element
customElements.define('editable-form', EditableForm);


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
                        <input type="text" class="small-input" placeholder="Add badge">
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
