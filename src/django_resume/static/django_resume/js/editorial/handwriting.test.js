import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { readFileSync } from 'node:fs';

const script = readFileSync('src/django_resume/static/django_resume/js/editorial/handwriting.js', 'utf8');
const css = readFileSync('src/django_resume/static/django_resume/css/editorial/handwriting.css', 'utf8');

let dom, win, svgs, observer, starts, timers;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(0);
  dom = new JSDOM(`<style>${css}</style><main>${['rail', 'lead', 'later'].map(id =>
    `<h2 class="${id === 'rail' ? 'cv-rail-label' : ''}"><span class="hw-text">${id}</span>
      <svg class="hw-svg" id="${id}"><g class="hw-ink-group"></g><path class="hw-pen"/></svg></h2>`
  ).join('')}</main>`, { runScripts: 'outside-only' });
  win = dom.window;
  win.Date.now = () => Date.now();
  starts = [];
  timers = [];
  win.setTimeout = (callback, delay) => {
    timers.push(callback); // Also allow delivery of a superseded callback LAST.
    return setTimeout(callback, delay);
  };
  win.document.documentElement.setAttribute('data-hw-replay-cooldown', '500');
  win.matchMedia = () => ({ matches: false });
  svgs = [...win.document.querySelectorAll('.hw-svg')];
  svgs.forEach(svg => {
    svg.getBoundingClientRect = () => ({ top: 10, bottom: 30 });
    svg.querySelector('.hw-pen').getTotalLength = () => 100;
    const add = svg.classList.add.bind(svg.classList);
    svg.classList.add = (...classes) => {
      if (classes.includes('hw-go')) starts.push(svg.id);
      return add(...classes);
    };
  });
  win.IntersectionObserver = class {
    constructor(callback) {
      this.callback = callback;
      this.observe = vi.fn();
      this.unobserve = vi.fn();
      this.disconnect = vi.fn();
      observer = this;
    }
  };
});

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
  dom.window.close();
});

function load() { win.eval(script); }
function enter(targets = svgs) {
  observer.callback(targets.map(target => ({ target, isIntersecting: true })));
}
function returnToTab() {
  for (const state of ['hidden', 'visible']) {
    Object.defineProperty(win.document, 'visibilityState', { value: state, configurable: true });
    win.document.dispatchEvent(new win.Event('visibilitychange'));
  }
}
function expectWritten(svg) {
  expect(win.getComputedStyle(svg.querySelector('.hw-ink-group')).visibility).toBe('visible');
  expect(win.getComputedStyle(svg.querySelector('.hw-pen')).getPropertyValue('stroke-dashoffset')).toBe('0');
}
function expectFailOpen() {
  expect(win.document.documentElement.classList.contains('js-hw')).toBe(false);
  svgs.forEach(expectWritten);
}

test.each(['throw', NaN, Infinity, -1])('measurement failure %s never hides any heading', failure => {
  // One label has already been armed when measurement of the next fails.
  svgs[1].querySelector('.hw-pen').getTotalLength = () => {
    if (failure === 'throw') throw new Error('measurement');
    return failure;
  };
  load();
  expectFailOpen();
});

test('observer construction failure stays readable', () => {
  win.IntersectionObserver = class { constructor() { throw new Error('constructor'); } };
  load();
  expectFailOpen();
});

test('observe failure disconnects and late callbacks cannot hide headings', () => {
  const Base = win.IntersectionObserver;
  win.IntersectionObserver = class extends Base {
    constructor(callback) {
      super(callback);
      this.observe.mockImplementation(() => { throw new Error('observe'); });
    }
  };
  load();
  expect(observer.disconnect).toHaveBeenCalledOnce();
  enter();
  returnToTab();
  vi.runAllTimers();
  expect(starts).toEqual([]);
  expectFailOpen();
});

test.each(['unobserve', 'reflow', 'timer'])('runtime %s failure opens all ink and disconnects', failure => {
  load();
  expect(win.document.documentElement.classList.contains('js-hw')).toBe(true);
  if (failure === 'unobserve') observer.unobserve.mockImplementation(() => { throw new Error('callback'); });
  if (failure === 'reflow') svgs[1].getBoundingClientRect = () => { throw new Error('reflow'); };
  if (failure === 'timer') svgs[0].getBoundingClientRect = () => { throw new Error('timer'); };
  enter();
  vi.runAllTimers();
  expect(observer.disconnect).toHaveBeenCalledOnce();
  const count = starts.length;
  enter();
  returnToTab();
  vi.runAllTimers();
  expect(starts).toHaveLength(count);
  expectFailOpen();
});

test('superseded timers are inert, including when delivered after the current timer', () => {
  load();
  enter();
  expect(starts).toEqual(['lead']);
  const stale = timers[0];
  vi.advanceTimersByTime(500); // replay while the first label is active
  returnToTab();
  expect(starts).toEqual(['lead', 'lead']);
  vi.advanceTimersByTime(751); // current lead finished, later is active
  expect(starts).toEqual(['lead', 'lead', 'later']);
  stale(); // stale delivery last must not advance the current queue
  expect(starts).toEqual(['lead', 'lead', 'later']);
  vi.runAllTimers();
  expect(starts).toEqual(['lead', 'lead', 'later', 'rail']);
});

test('cooldown excludes 499ms and admits exactly 500ms, for tab and top replay', () => {
  load();
  enter();
  vi.advanceTimersByTime(499);
  returnToTab();
  expect(starts).toEqual(['lead']);
  vi.advanceTimersByTime(1);
  returnToTab();
  expect(starts).toEqual(['lead', 'lead']);
  // An immediate scroll replay is also refused.
  function scroll(y) { win.scrollY = y; win.dispatchEvent(new win.Event('scroll')); }
  scroll(1000); scroll(0);
  expect(starts).toHaveLength(2);
  vi.advanceTimersByTime(500);
  scroll(1000); scroll(0);
  expect(starts).toEqual(['lead', 'lead', 'lead']);
});

test('a visible replay owns unseen labels before a queued observer batch arrives', () => {
  load();
  enter([svgs[1]]);
  vi.advanceTimersByTime(500);
  returnToTab(); // includes later and rail before their first observer delivery
  enter([svgs[0], svgs[2]]);
  vi.runAllTimers();
  expect(starts).toEqual(['lead', 'lead', 'later', 'rail']);
});

test('replay finishes superseded offscreen labels instead of leaving them hidden', () => {
  load();
  enter();
  svgs[0].getBoundingClientRect = () => ({ top: 10000, bottom: 10020 });
  vi.advanceTimersByTime(500);
  returnToTab();
  vi.runAllTimers();
  expectWritten(svgs[0]);
});

test('a removed queued label is skipped with its final ink intact', () => {
  load();
  enter();
  svgs[2].remove();
  vi.runAllTimers();
  expect(starts).toEqual(['lead', 'rail']);
  // Reinsert without invoking the observer; its final state must remain visible.
  win.document.body.append(svgs[2]);
  expectWritten(svgs[2]);
});
