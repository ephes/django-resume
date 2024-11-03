import {beforeEach, describe, expect, test, vi} from 'vitest';
import {screen, createEvent, fireEvent} from '@testing-library/dom';
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

    test('should update hidden inputs when contenteditable fields are edited and form is submitted', () => {
        const contentEditableTitle = screen.getByText('Original Title');

        // Simulate editing the contenteditable element
        contentEditableTitle.textContent = 'Updated Title';

        // Simulate clicking the submit button
        const submitButton = screen.getByText('Submit');
        fireEvent.click(submitButton);

        // Check that the hidden input is updated
        const hiddenInputTitle = document.querySelector('input[type="hidden"][data-field="title"]');
        expect(hiddenInputTitle.value).toBe('Updated Title');

        // Check that HTMX trigger was called to submit the form
        expect(window.htmx.trigger).toHaveBeenCalledWith(expect.anything(), 'submit');
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
            readAsDataURL: function () {
                this.onload({ target: { result: 'data:image/png;base64,dummydata' } });
            },
        };
        vi.spyOn(window, 'FileReader').mockImplementation(() => fileReaderMock);

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

    test('should update preview image when a file is drag-and-dropped onto the preview image', () => {
        const fileInput = document.getElementById('avatar-img');
        const previewImage = screen.getByAltText('Original Alt');

        // Create a mock File
        const file = new File(['dummy content'], 'example.png', { type: 'image/png' });

        // Mock FileReader
        const fileReaderMock = {
            onload: null,
            readAsDataURL: function () {
                this.onload({ target: { result: 'data:image/png;base64,dummydata' } });
            },
        };
        vi.spyOn(window, 'FileReader').mockImplementation(() => fileReaderMock);

        // Simulate dragover event to allow drop
        fireEvent.dragOver(previewImage);

        // Create a mock dataTransfer object
        const dataTransfer = {
            files: [file],
            types: ['Files'],
            getData: vi.fn(),
            setData: vi.fn(),
            clearData: vi.fn(),
        };

        // Simulate drop event with the mock dataTransfer
        const dropEvent = createEvent.drop(previewImage, {
            dataTransfer,
        });
        fireEvent(previewImage, dropEvent);

        // Check that the preview image src is updated
        expect(previewImage.src).toBe('data:image/png;base64,dummydata');

        // Since jsdom can't simulate updating fileInput.files via DataTransfer, we can't assert on fileInput.files
        // Instead, ensure that no errors were thrown and the image was updated
    });
});