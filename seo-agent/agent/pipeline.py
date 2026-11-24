"""Build one page end to end: research -> outline -> sections -> frame -> quality gates -> fact-check -> one improvement pass.
Hard problems (facts, filler, too short) block publishing; soft ones are listed in the PR for a human look."""
import time
from . import writer, quality, factcheck, research

def build(llm, facts, cfg, keyword, page_type, fetch=None, refresh=None, log=print):
    pause = cfg.get("llm_pause_seconds", 0)
    def call(system, user, **kw):
        out = llm.json(system, user, **kw)
        if pause: time.sleep(pause)
        return out

    questions = research.questions_for(keyword, fetch) if fetch else []
    log("Research: %d real questions" % len(questions))
    outline = writer.make_outline(call, facts, keyword, page_type, questions, refresh)
    if refresh: outline["slug"] = refresh["slug"]
    specs = (outline.get("sections") or [])[:9]
    titles = [s.get("h2", "") for s in specs]
    sections = [writer.make_section(call, facts, keyword, s, titles) for s in specs]
    frame = writer.make_frame(call, facts, keyword, outline, writer.digest_of(sections))
    draft = writer.assemble(outline, sections, frame)

    def evaluate(d):
        """-> (everything worth improving, what blocks publishing, quality report)"""
        probs = writer.validate(d, cfg)
        if probs:
            return probs, probs, None
        q = quality.report(d, keyword, cfg)
        fc = factcheck.check(d, facts, llm)
        return q["problems"] + fc, q["hard"] + fc, q

    improve, block, q = evaluate(draft)
    if improve:
        log("Improving once. Issues: %s" % improve)
        if q is None:                                   # structure problem: the frame is the usual culprit
            frame = writer.make_frame(call, facts, keyword, outline, writer.digest_of(sections), issues=improve)
            draft = writer.assemble(outline, sections, frame)
        else:
            thin = set(q["thin"])
            frame_text = " ".join(str(draft.get(k, "")) for k in ("intro", "key_takeaways", "faq", "comparison_table", "cta_text")).lower()
            frame_bad = [x for x in improve if x.split(": ")[-1].lower() in frame_text or x.startswith(("intro", "meta", "needs at least"))]
            targets = thin | set(writer.suspect_sections(draft, improve))
            if not targets and not frame_bad and not any(i.startswith(("title", "h1")) for i in improve):
                targets = set(range(len(draft["sections"])))      # location unknown: rewrite everything once
            for i in sorted(targets):
                spec = specs[i] if i < len(specs) else {"h2": draft["sections"][i]["h2"]}
                draft["sections"][i] = writer.make_section(call, facts, keyword, spec, titles, issues=improve,
                                                           previous=draft["sections"][i], min_words=300 if i in thin else None)
            if frame_bad:
                frame = writer.make_frame(call, facts, keyword, outline, writer.digest_of(draft["sections"]), issues=improve)
                kept = {k: draft[k] for k in ("slug", "title", "meta_description", "h1")}
                draft = writer.assemble(dict(outline, **kept), draft["sections"], frame)
        improve, block, q = evaluate(draft)
    if q is None:
        q = {"words": 0, "checks": {}, "thin": [], "problems": block, "hard": block, "section_words": []}
    return draft, block, q
