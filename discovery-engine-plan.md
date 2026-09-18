Discovery Engine — Build Plan & Findings (Task 1 / Phase 1)
This is the dedicated doc for the AI-powered discovery engine, separate from the overall project task plan.

1. Day 1 Pulse Check (informal web pass before the real pipeline)
Before building the full tagging/extraction pipeline, a manual web pass (Reddit threads, tech press synthesizing Reddit, Google Photos community forum, privacy blogs) to sanity check the problem is real and see what shape it takes. This is a small, journalist-curated sample, not a systematic pull, treat it as a hypothesis generator, not evidence to cite in the deck directly.

Major finding: Google already tried to solve exactly this problem, and reception is mixed to negative.

"Ask Photos," a Gemini-powered natural language search feature, launched in the US in 2024, promising queries like "what did we eat at the hotel in Stanley." It was paused in June 2025 over latency and quality issues, relaunched, and by March 2026 Google added a toggle to revert to "classic" search because complaints never fully died down. As of this year there are still large, active Reddit threads (1,000+ upvotes, 100+ comments) calling it a downgrade from the old keyword search.

This changes our framing. The MVP cannot just be "add conversational AI search," Google shipped that already and a meaningful share of users still reject it or find it unreliable. Our job is to find out why it fails when it does, and design around that specific mechanism, not just re-propose natural language search as if it were novel.

Four recurring patterns in the complaints:

Recall failure even with natural language. Users describe knowing they have hundreds of photos of something and Ask Photos surfacing only a handful, or a follow-up to a text-based OCR search ("find the photo with this word in it") no longer working as reliably as the old keyword search did.
Inconsistent, not uniformly broken. Some accounts describe Ask Photos working well for exactly our target scenario, vague, feeling-based queries like "photos from the Goa trip" succeeding without a remembered date. Others get poor results for similarly vague queries. This inconsistency, not a flat "it doesn't work," looks like the real story, and points at a reliability/grounding problem rather than a capability gap.
Manual scrolling is still the default workaround, independent of whether someone has tried the AI search at all. Multiple sources describe scrolling as a very common habit people don't even think to abandon.
A secondary, adjacent friction: trust. A non-trivial number of people turn off Gemini/Ask Photos features specifically over discomfort with AI reading personal photos, independent of whether the feature would actually help them. Worth tracking as a possible adoption blocker even if the retrieval mechanism itself is fixed later.
Useful business context found: Google Photos has 1.5 billion-plus monthly users storing 9 trillion-plus photos and videos, a real number worth using on slide 1 of the deck instead of an estimate.

What this pass could not cover (needs the real pipeline or manual effort outside this chat):

Bulk Play Store / App Store review text (star-rating reviews aren't crawlable at scale from here, would need a scraper run locally, or manual sampling from the app page)
YouTube comments (needs the YouTube Data API or manual sampling)
A truly random sample, this pass leans on threads tech journalists already found newsworthy, which skews toward extreme/viral complaints, not the average user's experience
2. Technical Build Plan (end to end)
Pipeline shape: Collect → Clean → Tag/Extract (LLM) → Synthesize/Score → Package & Deploy

Stack
Python 3.11, local scripts, no database needed at this scale (CSV/JSONL is fine)
google-play-scraper (pip) for Play Store reviews
app-store-scraper (pip) for App Store reviews
praw (pip) for Reddit, needs a free Reddit API app (reddit.com/prefs/apps, type "script") for a client id/secret
pandas for wrangling, python-dotenv for keys, tqdm for progress bars
anthropic (pip) for the Claude API tagging pass
Deployment for the required "testable link": a published interactive page (built directly in this chat, calling the Claude API live) is the fastest option and doubles as Deliverable 1. A Streamlit app on Streamlit Community Cloud is the alternative if a more "engineered dashboard" look is wanted.
A public GitHub repo with the scripts + PII-scrubbed data + README, this is what the reference deck's "GitHub Repo" link was doing, and it's evidence of real methodology, not just a claim
Repo structure
discovery-engine/
  .env
  requirements.txt
  README.md
  src/
    collect_playstore.py
    collect_appstore.py
    collect_reddit.py
    collect_manual_seed.py
    clean.py
    schema.py
    analyze.py
    synthesize.py
  data/
    raw/
    clean/
    tagged/
Stage 1: Collect
Play Store: google-play-scraper, app id com.google.android.apps.photos, pull recent reviews across all star ratings (don't pre-filter to negative only, that biases the sample before you've even started), aim for 2,000-3,000 rather than 10,000, quality of the discovery-focused subset matters more than raw count
App Store: app-store-scraper, same idea for iOS
Reddit: praw, search r/googlephotos, r/GooglePixel, r/Android, r/photography with queries like "can't find photo", "search doesn't work", "ask photos", "gemini search"; also pull the specific threads already found today by URL directly (full comment trees, not just the post)
Google Photos community/support forum: this is JS-rendered and doesn't scrape cleanly with simple requests (confirmed today), so hand-curate rather than build scraper infra for it, not worth the engineering time for the volume it'd add
YouTube comments: optional/stretch, needs a YouTube Data API key, skip unless time allows after everything else is done
Manual seed file: log the pulse-check findings above (Ask Photos threads, the scrolling-habit article, the "Goa trip" success story) as a small hand-curated CSV, these are already vetted, real, and detailed, legitimate seed data
Stage 2: Clean
Merge every source into one schema: [source, source_id, text, url, date, rating, pulled_at]
Deduplicate (exact + near-duplicate via normalized text hash)
Light PII scrub (regex for emails, phone numbers, @handles)
Keyword pre-filter to isolate the discovery-relevant subset (terms like search, find, can't locate, ask photos, gemini, remember, lost, old photo) before the expensive LLM pass, this recreates the "raw → cleaned → discovery-focused" funnel that makes the dataset table on the discovery slide credible
Stage 3: Tag/Extract (Claude)
JSON schema per record:

{
  "is_retrieval_story": bool,
  "memory_elements_present": ["place","time_window","event","people","object","emotion","visual_detail"],
  "memory_elements_missing": ["exact_date","album_name","filename","keyword"],
  "search_behavior": "typed_keyword | used_ask_photos | browsed_manually | used_face_search | used_location_search | did_not_attempt",
  "failure_point": "no_results | irrelevant_results | too_few_results | could_not_formulate_query | gave_up_before_searching | inconsistent_results | found_after_struggle",
  "workaround": "scrolled_manually | switched_to_classic_search | used_another_app | asked_family_friend | gave_up | none",
  "quote": "short verbatim snippet, under 15 words, for internal use",
  "confidence": "high | medium | low"
}
One prompt, run in batches with retry-on-malformed-JSON
Spot check the first ~20 outputs by hand before running the full batch, catches prompt issues early and cheaply
Stage 4: Synthesize
Frequency tables by failure_point and by memory-element pattern
An opportunity score per cluster: frequency �- specificity �- (optional) an intensity flag from the tagging
A findings.md with the ranked list and paraphrased supporting quotes, ready to lift into slide 2 of the deck
Stage 5: Package & deploy
Primary: a published interactive page (built in this chat) where someone can paste a real review/complaint and watch it get classified live against the schema above, this is the testable workflow link the brief asks for, and needs no separate hosting
Alternative: Streamlit app on Streamlit Community Cloud, more of a "dashboard" look if preferred
Either way: push code + PII-scrubbed data to a public GitHub repo as the methodology evidence
Execution sequence within the Phase 1 window
Day 1: repo/env setup, write and run the Play Store + Reddit collectors, log the manual seed file
Day 2: App Store collector (if time), cleaning script, keyword pre-filter
Day 3: LLM tagging pass, spot-check, fix prompt issues, run full batch
Day 4: synthesis, opportunity scoring, package the deployable demo, write findings.md, draft slide 2
If time gets tight: a lean fallback track
Skip the scraper infrastructure, expand the manual web-search harvesting to a larger curated sample (80-150 real snippets), run the same tagging schema by pasting batches into Claude conversationally instead of the API, synthesize by hand in a spreadsheet, and still ship the interactive demo page for Deliverable 1 (it doesn't depend on data volume). Lower ceiling, but honest and fully achievable without writing scraper code, and it can run in parallel with the full track rather than instead of it, if the collectors turn out to be slower than expected.

3. Does This Need to Run on a Schedule?
Short answer: not for the next 21 days, no. Worth designing for the deck, not worth actually operating right now.

Why not now: this pipeline exists to build one solid evidence base that Phase 2 through 4 get built on top of. App review and Reddit sentiment about a search feature doesn't meaningfully shift day to day, so re-running the full collector daily or weekly during a 3-week solo sprint burns engineering time without changing the findings. The one thing worth doing is making the pipeline re-runnable on demand: one entrypoint script, dedup logic already handles re-pulling the same sources without creating duplicates, so if a keyword gap turns up later (say interviews in Phase 3 surface a pattern the review data should also show), re-running it once is cheap. That's different from a scheduler, which runs itself on a timer whether you ask it to or not.

Where scheduling genuinely matters: if this were a real, shipped product feature rather than a research pass for a case study, a production version absolutely should run on a recurring cadence (say weekly), to catch emerging complaint patterns as Google ships changes to Ask Photos, and that's worth saying explicitly on the discovery-engine slide, it signals the pipeline was designed with production in mind, not just built once and thrown away.

If a real scheduled job is wanted anyway (for demo credibility, "look, it actually runs itself"), the cheap way to do it: a GitHub Actions workflow with a schedule: cron trigger (a few lines of YAML) that re-runs collect → clean → tag weekly and commits the refreshed data back to the repo. Free on GitHub, no server to keep running, and it's a real, verifiable artifact reviewers can check. This is genuinely optional scope, add it only if there's time left after the core pipeline works, not before.
