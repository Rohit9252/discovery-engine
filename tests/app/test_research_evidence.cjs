const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element(tag) {
  return {tag,children:[],textContent:'',append(...children){this.children.push(...children);},replaceChildren(...children){this.children=children;}};
}
const document = {createElement:element,addEventListener(){}};
const context = vm.createContext({document,URL});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../../src/app/static/research-evidence.js'),'utf8'),context);
const record = {review_id:'a',source:'reddit',relevance:'retrieval',rationale:'Search failure',
  evidence_quotes:['<img src=x onerror=alert(1)>'],remembered_clues:[],missing_details:[],attempted_queries:['searched dog'],
  workarounds:[],outcome:'failure',failure_mechanism:'poor_matches',source_text:'Original feedback',url:'javascript:alert(1)'};
const card=context.evidenceCard(record);
assert.equal(card.children.find(node=>node.tag==='blockquote').textContent,record.evidence_quotes[0]);
assert.equal(card.children.filter(node=>node.tag==='a').length,0);
const fields=card.children.find(node=>node.tag==='dl');
assert.equal(fields.children.length,4);
assert.equal(fields.children[1].children[1].textContent,'Not reported in this record');
assert.equal(fields.children[2].children[1].textContent,'searched dog');
assert.equal(card.children.find(node=>node.tag==='details').children[1].textContent,'Original feedback');
const linked=context.evidenceCard({...record,url:'https://reddit.com/comments/a'});
assert.equal(linked.children.at(-1).rel,'noopener noreferrer');
assert.equal(linked.children.at(-1).href,'https://reddit.com/comments/a');
console.log('Research evidence rendering tests passed');
