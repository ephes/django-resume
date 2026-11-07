import {afterEach, beforeEach, describe, expect, test, vi} from 'vitest';
import {screen, fireEvent} from '@testing-library/dom';
import '@testing-library/jest-dom';

// Import the web components
import './edit.js';

describe('BadgeEditor', () => {
    let component;

    beforeEach(() => {
        document.body.innerHTML = `
            <input type="hidden" id="badge-hidden-input" value='["Python", "Django"]' />
            <badge-editor input-field-id="badge-hidden-input"></badge-editor>
        `;

        component = document.querySelector('badge-editor');
        // Mock window.alert
        vi.spyOn(window, 'alert').mockImplementation(() => {
        });
    });

    test('should render initial badges correctly', () => {
        const badges = screen.getAllByText(/Python|Django/);
        expect(badges.length).toBe(2);
    });

    test('should add a new badge', async () => {
        const input = screen.getByPlaceholderText('Add badge');
        const addButton = screen.getByText('Add');

        // Add a new badge
        fireEvent.change(input, {target: {value: 'JavaScript'}});
        fireEvent.click(addButton);

        // Check that the badge was added to the list
        const newBadge = screen.getByText('JavaScript');
        expect(newBadge).toBeInTheDocument();
    });

    test('should prevent adding duplicate badges', () => {
        const input = screen.getByPlaceholderText('Add badge');
        const addButton = screen.getByText('Add');

        // Try to add an existing badge
        fireEvent.change(input, {target: {value: 'Python'}});
        fireEvent.click(addButton);

        // Check for an alert
        expect(window.alert).toHaveBeenCalledWith('Badge already exists.');
    });

    test('should update hidden input field when badge is added', () => {
        const input = screen.getByPlaceholderText('Add badge');
        const addButton = screen.getByText('Add');

        // Add a new badge
        fireEvent.change(input, {target: {value: 'JavaScript'}});
        fireEvent.click(addButton);

        // Check that the hidden input is updated
        const hiddenInput = document.getElementById('badge-hidden-input');
        expect(hiddenInput.value).toBe(JSON.stringify(['Python', 'Django', 'JavaScript']));
    });

    test('should remove a badge when delete button is clicked', () => {
        const deleteButton = screen.getAllByRole('button', {name: /delete/i})[0];

        // Delete the first badge
        fireEvent.click(deleteButton);

        // Check that the badge was removed
        const deletedBadge = screen.queryByText('Python');
        expect(deletedBadge).not.toBeInTheDocument();
    });
});


beforeAll(() => {
    class DataTransferMock {
        constructor() {
            this.files = [];
            this.items = {
                add: (file) => {
                    this.files.push(file);
                },
                remove: (index) => {
                    this.files.splice(index, 1);
                },
                get length() {
                    return this.files.length;
                },
            };
        }
    }

    global.DataTransfer = DataTransferMock;
});

describe('EditableForm', () => {
    let component;

    beforeEach(() => {
        document.body.innerHTML = `
            <editable-form id="test-form">
              <form id="form-test" hx-post="/submit-url" hx-target="#test-form" hx-swap="outerHTML">
                <input type="hidden" data-field="title" name="title" value="Original Title">
                <input type="file" id="avatar-img" style="display:none;" name="avatar_img" accept="image/*"/>
                <input type="hidden" data-field="avatar_alt" name="avatar_alt" value="Original Alt">
              </form>
              <header>
                <div>
                  <h1 contenteditable="true" data-field="title">Original Title</h1>
                </div>
              </header>
              <div class="stack">
                <div id="avatar-container" class="avatar-container">
                  <div class="stack">
                    <img class="avatar editable-avatar" data-field="avatar_img" src="" alt="Original Alt">
                    <p contenteditable="true" data-field="avatar_alt">Original Alt</p>
                  </div>
                </div>
                <div>
                  <button id="submit-button" type="submit">Submit</button>
                </div>
              </div>
            </editable-form>
        `;

        // Mock HTMX
        window.htmx = {
            trigger: vi.fn(),
        };

        component = document.querySelector('editable-form');
    });

    test('should render the component correctly', () => {
        const editableForm = document.querySelector('editable-form');
        expect(editableForm).toBeInTheDocument();

        const formElement = editableForm.querySelector('form');
        expect(formElement).toBeInTheDocument();

        const contentEditableTitle = screen.getByText('Original Title');
        expect(contentEditableTitle).toBeInTheDocument();

        const hiddenInputTitle = formElement.querySelector('input[type="hidden"][data-field="title"]');
        expect(hiddenInputTitle).toBeInTheDocument();
        expect(hiddenInputTitle.value).toBe('Original Title');
    });

    afterEach(() => {
        document.body.replaceChildren();
        vi.restoreAllMocks();
    });

    test('an external Save button works when an integration supplies no form id', () => {
        component.remove();
        const form = component.querySelector('form');
        form.removeAttribute('id');
        component.querySelector('button').removeAttribute('form');
        const existing = document.createElement('div');
        existing.id = 'editable-form-1';
        document.body.append(existing, component);
        const submitted = vi.fn((event) => event.preventDefault());
        form.addEventListener('submit', submitted);
        component.querySelector('button').click();
        expect(submitted).toHaveBeenCalledTimes(1);
        expect(component.querySelector('button').form).toBe(form);
        expect(existing.id).toBe('editable-form-1');
    });

    test.each(['click', 'native submit', 'requestSubmit'])(
        '%s synchronizes text and HTML before one submit reaches HTMX', (method) => {
            const form = component.querySelector('form');
            component.querySelector('[data-field="title"][contenteditable]').innerHTML = ' New &amp; <b>bold</b> ';
            const rich = document.createElement('div');
            rich.contentEditable = 'true';
            rich.setAttribute('contenteditable', 'true');
            rich.dataset.field = 'description';
            rich.dataset.type = 'html';
            rich.innerHTML = ' <b>Rich &amp; text</b> ';
            component.append(rich);
            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'description';
            hidden.dataset.field = 'description';
            form.append(hidden);
            const submissions = [];
            // Stand in for HTMX's bubbling submit listener and serialization.
            form.addEventListener('submit', (event) => {
                event.preventDefault();
                submissions.push(Object.fromEntries(new FormData(form)));
            });
            if (method === 'click') component.querySelector('button').click();
            if (method === 'native submit') fireEvent.submit(form);
            if (method === 'requestSubmit') form.requestSubmit();
            expect(submissions).toHaveLength(1);
            expect(submissions[0]).toMatchObject({title: 'New & bold', description: '<b>Rich &amp; text</b>'});
            expect(window.htmx.trigger).not.toHaveBeenCalled();
        }
    );

    test.each(['click', 'requestSubmit'])('%s preserves native constraint validation', (method) => {
        const form = component.querySelector('form');
        const required = document.createElement('input');
        required.required = true;
        form.append(required);
        const submitted = vi.fn((event) => event.preventDefault());
        form.addEventListener('submit', submitted);
        if (method === 'click') component.querySelector('button').click();
        else form.requestSubmit();
        expect(submitted).not.toHaveBeenCalled();
        expect(window.htmx.trigger).not.toHaveBeenCalled();
        required.value = 'valid';
        if (method === 'click') component.querySelector('button').click();
        else form.requestSubmit();
        expect(submitted).toHaveBeenCalledTimes(1);
    });

    test('reconnections own one set of listeners and detached controls do no work', () => {
        const form = component.querySelector('form');
        const hidden = component.querySelector('input[data-field="title"]');
        const titleWrite = vi.spyOn(hidden, 'value', 'set');
        component.remove();
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.dataset.field = 'enabled';
        const enabled = document.createElement('input');
        enabled.type = 'hidden';
        enabled.dataset.field = 'enabled';
        form.append(enabled);
        component.append(checkbox);
        const toggleWrite = vi.spyOn(enabled, 'value', 'set');
        document.body.append(component);
        for (let i = 0; i < 3; i++) {
            component.remove();
            document.body.append(component);
        }
        const preview = component.querySelector('.editable-avatar');
        const fileInput = component.querySelector('input[type="file"]');
        const picker = vi.spyOn(fileInput, 'click').mockImplementation(() => {});
        const read = vi.fn();
        vi.spyOn(window, 'FileReader').mockImplementation(function () {
            return {readAsDataURL: read, abort: vi.fn()};
        });
        Object.defineProperty(fileInput, 'files', {value: [new File(['image'], 'synthetic.png')], configurable: true});
        form.addEventListener('submit', (event) => event.preventDefault());
        component.querySelector('button').click();
        fireEvent.change(checkbox, {target: {checked: true}});
        fireEvent.click(preview);
        fireEvent.change(fileInput);
        expect(titleWrite).toHaveBeenCalledTimes(1);
        expect(toggleWrite).toHaveBeenCalledTimes(1);
        expect(enabled.value).toBe('on');
        expect(picker).toHaveBeenCalledTimes(1);
        expect(read).toHaveBeenCalledTimes(1);
        component.remove();
        fireEvent.submit(form);
        fireEvent.change(checkbox);
        fireEvent.click(preview);
        fireEvent.change(fileInput);
        expect(titleWrite).toHaveBeenCalledTimes(1);
        expect(toggleWrite).toHaveBeenCalledTimes(1);
        expect(picker).toHaveBeenCalledTimes(1);
        expect(read).toHaveBeenCalledTimes(1);
    });

    function controlledReaders(onRead = () => {}) {
        const readers = [];
        vi.spyOn(window, 'FileReader').mockImplementation(function () {
            const reader = {
                readAsDataURL: vi.fn(onRead), abort: vi.fn(),
                complete(value) { this.onload({target: {result: value}}); }
            };
            readers.push(reader);
            return reader;
        });
        return readers;
    }

    function select(file) {
        const input = component.querySelector('input[type="file"]');
        Object.defineProperty(input, 'files', {value: file ? [file] : [], configurable: true});
        fireEvent.change(input);
        return input;
    }

    test('the newest selected file owns the preview, including stale error and abort callbacks', () => {
        const readers = controlledReaders();
        const first = new File(['A'], 'a.png');
        const second = new File(['B'], 'b.png');
        select(first);
        const input = select(second);
        expect(readers[0].abort).toHaveBeenCalledTimes(1);
        readers[1].complete('data:image/png;base64,Qg==');
        readers[0].complete('data:image/png;base64,QQ==');
        readers[0].onerror();
        readers[0].onabort();
        expect(component.querySelector('img').src).toBe('data:image/png;base64,Qg==');
        expect(input.files[0]).toBe(second);
        expect(component.querySelector('[role="status"]')?.textContent || '').toBe('');
    });

    test.each(['error', 'abort', 'throw'])('read %s preserves selection and prior preview with one bounded message', (failure) => {
        const readers = controlledReaders(() => {
            if (failure === 'throw') throw new Error('private diagnostic');
        });
        const file = new File(['A'], 'synthetic.png');
        const preview = component.querySelector('img');
        preview.src = 'data:image/png;base64,b2xk';
        const input = select(file);
        const active = readers.at(-1);
        if (failure === 'error') active.onerror();
        if (failure === 'abort') active.onabort();
        expect(input.files[0]).toBe(file);
        expect(preview.src).toBe('data:image/png;base64,b2xk');
        const status = component.querySelector('[role="status"]');
        expect(status.textContent).toMatch(/preview/i);
        expect(status.textContent.length).toBeLessThan(150);
        expect(status.textContent).not.toContain('private diagnostic');
        select(file);
        expect(component.querySelectorAll('[role="status"]').length).toBeLessThanOrEqual(1);
    });

    test('clearing a selection and disconnecting invalidate pending readers', () => {
        const readers = controlledReaders();
        const file = new File(['A'], 'a.png');
        const preview = component.querySelector('img');
        select(file);
        select(null);
        expect(readers[0].abort).toHaveBeenCalledTimes(1);
        readers[0].complete('data:image/png;base64,QQ==');
        expect(preview.getAttribute('src')).toBe('');
        select(file);
        component.remove();
        expect(readers[1].abort).toHaveBeenCalledTimes(1);
        document.body.append(component);
        readers[1].complete('data:image/png;base64,QQ==');
        expect(preview.getAttribute('src')).toBe('');
    });

    test('should update hidden inputs when contenteditable fields are edited and form is submitted', () => {
        const contentEditableTitle = screen.getByText('Original Title');

        // Simulate editing the contenteditable element
        contentEditableTitle.textContent = 'Updated Title';

        component.querySelector('form').addEventListener('submit', (event) => event.preventDefault());
        // Simulate clicking the submit button
        const submitButton = screen.getByText('Submit');
        fireEvent.click(submitButton);

        // Check that the hidden input is updated
        const hiddenInputTitle = document.querySelector('input[type="hidden"][data-field="title"]');
        expect(hiddenInputTitle.value).toBe('Updated Title');

        // HTMX observes the native submit event; the component must not synthesize another.
        expect(window.htmx.trigger).not.toHaveBeenCalled();
    });

    test('should open file picker when clicking on the preview image', () => {
        const fileInput = document.getElementById('avatar-img');
        const previewImage = screen.getByAltText('Original Alt');

        // Mock the click function of file input
        vi.spyOn(fileInput, 'click').mockImplementation(() => {});

        // Simulate clicking on the preview image
        fireEvent.click(previewImage);

        // Check that fileInput.click() was called
        expect(fileInput.click).toHaveBeenCalled();
    });

    test('should update preview image when a file is selected', () => {
        const fileInput = document.getElementById('avatar-img');
        const previewImage = screen.getByAltText('Original Alt');

        // Create a mock File
        const file = new File(['dummy content'], 'example.png', { type: 'image/png' });

        // Mock FileReader
        const fileReaderMock = {
            onload: null,
            abort: vi.fn(),
            readAsDataURL: function () {
                this.onload({ target: { result: 'data:image/png;base64,dummydata' } });
            },
        };
        vi.spyOn(window, 'FileReader').mockImplementation(function () { return fileReaderMock; });

        // Directly set the files property
        Object.defineProperty(fileInput, 'files', {
            value: [file],
            writable: false,
        });

        // Simulate change event
        fireEvent.change(fileInput);

        // Check that the preview image src is updated
        expect(previewImage.src).toBe('data:image/png;base64,dummydata');
    });

    function drop(preview, file) {
        // Construct the event independently of the DataTransfer API under test.
        const event = new Event('drop', {bubbles: true, cancelable: true});
        Object.defineProperty(event, 'dataTransfer', {value: {files: [file]}});
        fireEvent(preview, event);
    }

    test.each(['construct', 'add', 'assign', 'ignored assignment'])(
        'failed drop (%s) preserves the actual file and preview and requests the picker', (failure) => {
            const readers = controlledReaders();
            const input = component.querySelector('input[type="file"]');
            const preview = component.querySelector('img');
            const oldFile = new File(['old'], 'old.png');
            const dropped = new File(['new'], 'new.png');
            preview.src = 'data:image/png;base64,b2xk';
            Object.defineProperty(input, 'files', {
                configurable: true,
                get: () => [oldFile],
                set: () => {
                    if (failure === 'assign') throw new Error('synthetic assignment failure');
                }
            });
            vi.spyOn(window, 'DataTransfer').mockImplementation(function () {
                if (failure === 'construct') throw new Error('synthetic construction failure');
                return {files: [dropped], items: {add() {
                    if (failure === 'add') throw new Error('synthetic add failure');
                }}};
            });
            drop(preview, dropped);
            expect(input.files[0]).toBe(oldFile);
            expect(preview.src).toBe('data:image/png;base64,b2xk');
            expect(readers).toHaveLength(0);
            expect(component.querySelector('[role="status"]').textContent).toMatch(/file picker/i);
            expect(preview).not.toHaveClass('drag-over');
        }
    );

    test('successful drop commits the exact file before reading and replaces SVG previews with owned listeners', () => {
        const readers = controlledReaders((file) => {
            expect(input.files[0]).toBe(file);
        });
        const input = component.querySelector('input[type="file"]');
        component.querySelector('img').outerHTML = '<svg class="editable-avatar" data-field="avatar_img" width="110" height="100"></svg>';
        // Reconnect so the SVG is the preview bound by the component.
        component.remove();
        document.body.append(component);
        const preview = component.querySelector('svg');
        let files = [];
        Object.defineProperty(input, 'files', {get: () => files, set: (value) => {files = value;}, configurable: true});
        const dropped = new File(['image'], 'synthetic.png', {type: 'image/png'});
        fireEvent.dragOver(preview);
        expect(preview).toHaveClass('drag-over');
        drop(preview, dropped);
        expect(input.files[0]).toBe(dropped);
        expect(readers).toHaveLength(1);
        expect(readers[0].readAsDataURL).toHaveBeenCalledWith(dropped);
        readers[0].complete('data:image/png;base64,aW1hZ2U=');
        const replacement = component.querySelector('img');
        expect(replacement.src).toBe('data:image/png;base64,aW1hZ2U=');
        expect(replacement).toHaveAttribute('width', '110');
        expect(replacement).toHaveAttribute('height', '100');
        const picker = vi.spyOn(input, 'click').mockImplementation(() => {});
        fireEvent.click(replacement);
        expect(picker).toHaveBeenCalledTimes(1);
        component.remove();
        fireEvent.click(replacement);
        expect(picker).toHaveBeenCalledTimes(1);
    });
});
