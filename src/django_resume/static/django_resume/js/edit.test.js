import { beforeEach, describe, expect, test, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/dom';
import '@testing-library/jest-dom';

// Import the web component
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
        vi.spyOn(window, 'alert').mockImplementation(() => {});
    });

    test('should render initial badges correctly', () => {
        const badges = screen.getAllByText(/Python|Django/);
        expect(badges.length).toBe(2);
    });

    test('should add a new badge', async () => {
        const input = screen.getByPlaceholderText('Add badge');
        const addButton = screen.getByText('Add');

        // Add a new badge
        fireEvent.change(input, { target: { value: 'JavaScript' } });
        fireEvent.click(addButton);

        // Check that the badge was added to the list
        const newBadge = screen.getByText('JavaScript');
        expect(newBadge).toBeInTheDocument();
    });

    test('should prevent adding duplicate badges', () => {
        const input = screen.getByPlaceholderText('Add badge');
        const addButton = screen.getByText('Add');

        // Try to add an existing badge
        fireEvent.change(input, { target: { value: 'Python' } });
        fireEvent.click(addButton);

        // Check for an alert
        expect(window.alert).toHaveBeenCalledWith('Badge already exists.');
    });

    test('should update hidden input field when badge is added', () => {
        const input = screen.getByPlaceholderText('Add badge');
        const addButton = screen.getByText('Add');

        // Add a new badge
        fireEvent.change(input, { target: { value: 'JavaScript' } });
        fireEvent.click(addButton);

        // Check that the hidden input is updated
        const hiddenInput = document.getElementById('badge-hidden-input');
        expect(hiddenInput.value).toBe(JSON.stringify(['Python', 'Django', 'JavaScript']));
    });

    test('should remove a badge when delete button is clicked', () => {
        const deleteButton = screen.getAllByRole('button', { name: /delete/i })[0];

        // Delete the first badge
        fireEvent.click(deleteButton);

        // Check that the badge was removed
        const deletedBadge = screen.queryByText('Python');
        expect(deletedBadge).not.toBeInTheDocument();
    });
});
