const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const nodes = new Map();
const document = {
  getElementById(id) {
    if (!nodes.has(id)) nodes.set(id, {textContent:'', children:[], replaceChildren(...children) { this.children = children; }});
    return nodes.get(id);
  },
  createElement() { return {textContent:''}; },
};
const context = vm.createContext({document});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../src/app/static/research-status.js'), 'utf8'), context);
context.renderResearchStatus({state:'pending_review', title:'Analysis not yet reviewed', details:['Source checks pending','<b>verbatim text</b>'], next_steps:['Check context','Calibrate labels']});
assert.equal(nodes.get('stat-stages').textContent, 'Not assessed');
assert.equal(nodes.get('analysis-state-label').textContent, 'Ready to analyze');
assert.equal(nodes.get('hero-opportunities').children.length, 2);
assert.equal(nodes.get('hero-pain-points').children[1].textContent, '<b>verbatim text</b>');
context.renderResearchStatus({state:'no_data', title:'No feedback collected', details:[], next_steps:[]});
assert.equal(nodes.get('analysis-state-label').textContent, 'No data');
assert.equal(nodes.get('hero-opportunities').children.length, 1);
assert.throws(() => context.renderResearchStatus(undefined), /missing or unsupported/);
context.renderResearchStatus({state:'running',title:'Analyzing',details:['In progress'],next_steps:['Inspect evidence'],retrieval_count:12,analyzed_count:30,total:100,pending_count:62,failed_count:8,incomplete_memory_count:3});
assert.equal(nodes.get('analysis-state-label').textContent,'Analyzing');
assert.equal(nodes.get('stat-stages').textContent,'12');
assert.match(nodes.get('analysis-checklist').children[0].textContent,/30 \/ 100/);
context.renderResearchStatus({state:'completed',title:'Complete',details:[],next_steps:[],retrieval_count:0});
assert.equal(nodes.get('stat-stages').textContent,'0');
assert.equal(nodes.get('analysis-state-label').textContent,'AI analysis complete');
context.renderResearchStatus({state:'paused',title:'Paused',details:['Saved findings preserved'],next_steps:['Resume after approval'],retrieval_count:10});
assert.equal(nodes.get('analysis-state-label').textContent,'Paused by you');
console.log('Research status rendering tests passed');
