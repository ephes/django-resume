// Preserve browser-created lines without interpreting literal markup as HTML.
const PLAIN_BLOCKS = new Set(['DIV', 'P', 'LI', 'UL', 'OL', 'BLOCKQUOTE', 'PRE',
    'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'SECTION', 'ARTICLE', 'HEADER', 'FOOTER']);
function plainEditorText(node) {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent;
    if (node.nodeType !== Node.ELEMENT_NODE) return '';
    if (node.tagName === 'BR') return '\n';
    let text = '';
    let previousBlock = false;
    for (const child of node.childNodes) {
        // Formatting whitespace between pasted blocks is not an extra line.
        if (child.nodeType === Node.TEXT_NODE && !child.textContent.trim()
            && (previousBlock || PLAIN_BLOCKS.has(child.nextSibling?.nodeName))) continue;
        const block = PLAIN_BLOCKS.has(child.nodeName);
        if ((block || previousBlock) && text && !text.endsWith('\n')) text += '\n';
        text += plainEditorText(child);
        previousBlock = block;
    }
    return text;
}

class EditableForm extends HTMLElement {
    constructor() {
        super();
    }

    connectedCallback() {
        this.listeners = new AbortController();
        const options = {signal: this.listeners.signal};

        // Access elements within the component
        const formElement = this.querySelector('form');
        const submitButton = this.querySelector('button[type="submit"]');
        const checkboxes = this.querySelectorAll('input[type="checkbox"]');
        const syncCheckbox = (checkbox) => {
            const field = checkbox.dataset.field || checkbox.name;
            if (!field) return;
            const hiddenInput = Array.from(formElement.querySelectorAll('input[type="hidden"]'))
                .find(input => (input.dataset.field || input.name) === field);
            if (hiddenInput) hiddenInput.value = checkbox.checked ? "on" : "";
        };
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => syncCheckbox(checkbox), options);
        });

        // Built-in templates keep Save outside the hidden form. Give it native
        // form ownership so clicks use the same validation/submit path as keyboards.
        // Read the attribute: item forms post a field named "id", which shadows form.id.
        if (submitButton && !submitButton.form) {
            let formId = formElement.getAttribute('id');
            if (!formId) {
                let index = 1;
                while (document.getElementById(`editable-form-${index}`)) index++;
                formId = `editable-form-${index}`;
                formElement.setAttribute('id', formId);
            }
            submitButton.setAttribute('form', formId);
        }

        // Capture runs before HTMX's bubbling listener serializes the form.
        formElement.addEventListener('submit', () => {
            checkboxes.forEach(syncCheckbox);
            // Collect data from contenteditable elements
            this.querySelectorAll('[contenteditable="true"]').forEach((field) => {
                const fieldName = field.dataset.field;
                const fieldType = field.dataset.type;
                let fieldValue;

                if (fieldType === "html") {
                    fieldValue = field.innerHTML.trim();
                } else {
                    fieldValue = plainEditorText(field).trim();
                }

                // Update the corresponding hidden input field
                const hiddenInput = formElement.querySelector(`input[type="hidden"][data-field="${fieldName}"]`);
                if (hiddenInput) {
                    hiddenInput.value = fieldValue;
                }
            });
        }, {...options, capture: true});

        // Handle file inputs and their preview elements
        const fileInputs = this.querySelectorAll('input[type="file"]');

        fileInputs.forEach((fileInput) => {
            this.setupFileInput(fileInput);
        });
    }

    disconnectedCallback() {
        this.listeners.abort();
    }

    setupFileInput(fileInput) {
        const options = {signal: this.listeners.signal};
        const fieldName = fileInput.name;
        const previewElements = Array.from(this.querySelectorAll(`.editable-avatar[data-field="${fieldName}"]`));

        let currentReader = null;
        // Mount an empty live region before any failure needs announcing.
        const status = document.createElement('p');
        status.setAttribute('role', 'status');
        this.append(status);
        const showStatus = (message) => {
            status.textContent = message;
        };
        const clearStatus = () => {
            status.textContent = '';
        };
        const cancelRead = () => {
            const reader = currentReader;
            currentReader = null;
            if (reader) reader.abort();
        };
        options.signal.addEventListener('abort', () => {
            cancelRead();
            status.remove();
        }, {once: true});

        const addEventListenersToPreviewElement = (previewElement) => {
            previewElement.addEventListener('click', () => {
                fileInput.click();
            }, options);

            previewElement.addEventListener('dragover', (event) => {
                event.preventDefault();
                previewElement.classList.add('drag-over');
            }, options);

            previewElement.addEventListener('dragleave', () => {
                previewElement.classList.remove('drag-over');
            }, options);

            previewElement.addEventListener('drop', (event) => {
                event.preventDefault();
                previewElement.classList.remove('drag-over');
                const file = event.dataTransfer.files[0];
                if (file && updateFileInput(file)) {
                    handleFileUpload(file);
                }
            }, options);
        };

        const handleFileUpload = (file) => {
            cancelRead();
            clearStatus();
            const reader = new FileReader();
            currentReader = reader;
            reader.onload = (event) => {
                if (currentReader !== reader) return;
                currentReader = null;
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
            const fail = () => {
                if (currentReader !== reader) return;
                currentReader = null;
                showStatus('Could not preview this image. Choose a file again.');
            };
            reader.onerror = fail;
            reader.onabort = fail;
            try {
                reader.readAsDataURL(file);
            } catch (error) {
                fail();
            }
        };

        const updateFileInput = (file) => {
            try {
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                fileInput.files = dataTransfer.files;
                if (fileInput.files[0] === file) return true;
            } catch (error) {
                // Unsupported browsers must retain the submitted selection/preview.
            }
            showStatus('Could not select the dropped image. Use the file picker.');
            return false;
        };

        previewElements.forEach((previewElement) => {
            addEventListenersToPreviewElement(previewElement);
        });

        fileInput.addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (file) {
                handleFileUpload(file);
            } else {
                cancelRead();
                clearStatus();
            }
        }, options);
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
// Keep in sync with plugins/badges.py: Unicode code points, not UTF-16 units.
const BADGE_LIMITS = {count: 1024, length: 1024, text: 65536};
function validBadges(badges) {
    if (!Array.isArray(badges) || badges.length > BADGE_LIMITS.count) return false;
    let total = 0;
    for (const badge of badges) {
        if (typeof badge !== 'string') return false;
        // Count with early refusal rather than allocating a code-point array.
        let length = 0;
        for (const point of badge) {
            if (++length > BADGE_LIMITS.length || ++total > BADGE_LIMITS.text) return false;
        }
    }
    return true;
}

class BadgeEditor extends HTMLElement {
    constructor() {
        super();
    }

    showError(message) {
        let status = this.querySelector('[role="alert"]');
        if (!status) {
            status = document.createElement('p');
            status.setAttribute('role', 'alert');
            this.append(status);
        }
        status.textContent = message;
    }

    render() {
        if (!this.isConnected) return;
        const pending = this.querySelector('input.small-input')?.value || '';
        this.listeners?.abort();
        this.listeners = new AbortController();
        const options = {signal: this.listeners.signal};
        const owner = this.closest('editable-form');
        const form = owner?.querySelector('form');
        const targets = form ? Array.from(form.querySelectorAll('input'))
            .filter(input => input.id === this.inputFieldId) : [];
        let ready = false;
        // Capture precedes HTMX serialization, including listeners installed
        // before custom-element upgrade. A refused draft stays on screen.
        form?.addEventListener('submit', event => {
            if (!ready || !this.commitPending()) {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        }, {...options, capture: true});
        if (targets.length !== 1 || targets[0].type !== 'hidden') {
            this.showError('Badge target is missing or ambiguous. Reload this form.');
            return;
        }
        const hidden = targets[0];
        let badges;
        try {
            badges = JSON.parse(hidden.value);
            if (!validBadges(badges)) throw new Error('Invalid badges');
        } catch {
            this.showError('Stored badges exceed the list/text limits or are invalid. '
                + 'Correct them elsewhere, or clear them to save this form.');
            // Explicit recovery: never discard stored data without a user action,
            // but do not leave the owning form permanently unsavable.
            this.querySelector('button.badge-clear-button')?.remove();
            const clear = document.createElement('button');
            clear.type = 'button';
            clear.className = 'badge-clear-button';
            clear.textContent = 'Clear badges';
            clear.addEventListener('click', event => {
                event.preventDefault();
                hidden.value = '[]';
                this.render();
            }, options);
            this.append(clear);
            return;
        }
        // Admission happens before replacing any existing editing DOM.
        this.innerHTML = `
            <ul class="cluster cluster-list">
                <li><input type="text" class="small-input" placeholder="Add badge">
                    <button type="button">Add</button></li>
            </ul><p role="alert"></p>`;
        const input = this.querySelector('input');
        input.value = pending;
        const list = this.querySelector('ul');
        if (this.ulClass) list.classList.add(this.ulClass);
        this.renderBadgesList(badges);
        this.commitPending = () => {
            const badge = input.value.trim();
            if (!badge) return true;
            if (badges.includes(badge)) {
                this.showError('Badge already exists.');
                return false;
            }
            const proposed = [...badges, badge];
            if (!validBadges(proposed)) {
                this.showError('Badge count or text limit exceeded. Shorten or remove badges.');
                return false;
            }
            badges = proposed;
            list.insertBefore(this.getBadgeLi(badge), list.lastElementChild);
            hidden.value = JSON.stringify(badges);
            input.value = '';
            this.showError('');
            return true;
        };
        this.querySelector('li:last-child button').addEventListener('click', event => {
            event.preventDefault();
            this.commitPending();
        }, options);
        input.addEventListener('keydown', event => {
            if (event.key === 'Enter' && !event.isComposing) {
                event.preventDefault();
                this.commitPending();
            }
        }, options);
        input.addEventListener('input', () => this.showError(''), options);
        list.addEventListener('click', event => {
            const button = event.target.closest('.badge-delete-button');
            if (!button || !list.contains(button)) return;
            event.preventDefault();
            const li = button.closest('li');
            const index = Array.from(list.children).indexOf(li);
            badges.splice(index, 1);
            li.remove();
            hidden.value = JSON.stringify(badges);
            this.showError('');
        }, options);
        ready = true;
    }

    disconnectedCallback() {
        this.listeners?.abort();
    }

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
