import os
import re
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq

# ─────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Proofreader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY_VALIDATOR = os.environ.get("GROQ_API_KEY_VALIDATOR", "")
GROQ_API_KEY_FIXER     = os.environ.get("GROQ_API_KEY_FIXER", "")
MODEL = "openai/gpt-oss-120b"   # closest publicly available Groq model
                                     # swap to any Groq model you have access to

client_validator = Groq(api_key=GROQ_API_KEY_VALIDATOR)
client_fixer     = Groq(api_key=GROQ_API_KEY_FIXER)

# ─────────────────────────────────────────────
# Prompts (extracted verbatim from your n8n workflow)
# ─────────────────────────────────────────────
MISTAKE_FINDER_PROMPT = """Role: You are a Strict Quality Assurance (QA) and Grammar Auditor for coding problems.
Objective: Analyze the provided "Coding Question" and validate it against the Style & Formatting Guide defined below.
Output: Produce a categorized Error Report using the exact template provided at the end.

STYLE & FORMATTING GUIDE (The Rules)
1. Global Formatting Rules
\t-Array Formatting: Must look like A[i] = [1, 3, 5, 8].
\t-String Formatting: Must look like S = "abc".

2. Grammar & Language Mechanics
\t- Professional Tone: Text must be free of spelling mistakes, typos, and grammatical errors (subject-verb agreement, punctuation).
\t- Clarity: Sentences in the Problem Statement and Explanation must be clear and logical.
\t- Technical Exceptions: Do not flag standard technical notation (e.g., variables like N, A[i], math ranges, or phrases like "space-separated integers") as grammar errors.
\t- Math Notation Exception: Do NOT flag ^ as an error. In this context ^ always means "raised to the power of" (exponentiation). Never treat ^ as multiplication.

3. Section Sequence & Specific Requirements
The content must follow this exact order. If a section is missing (unless optional), it is an error.
\t1. Title:
\t\t~Constraint: No section header (e.g., do not write "Title").
\t2. Problem Statement:
\t\t~Constraint: No section header.
\t\t~Content: Story-building/input definition.
\t\t~Ending: The last sentence must be the main task/objective. It must end with a period (.), never a question mark (?).
\t3. Note: (Optional)
\t\t~Header: Note
\t\t~Constraint: Only include if original question had it.
\t4. Example: (Optional)
\t\t~Header: Example
\t\t~Constraint: Only include if original question had it.
\t5. Function Description:
\t\t~Header: Function Description
\t\t~Boilerplate Requirement: The text MUST follow this exact template (variables in brackets [] are the only allowed changes):"In the provided code snippet, implement the provided [FUNCTION_NAME] method using the variables to print the [TASK_DESCRIPTION]. You can write your code in the space below the phrase "WRITE YOUR LOGIC HERE". There will be multiple test cases running so the Input and Output should match exactly as provided. The base Output variable result is set to a default value of -404 which can be modified. Additionally, you can add or remove these output variables."
\t6. Input Format:
\t\t~Header: Input Format
\t\t~Content: Variable definitions (e.g., "The first line contains...").
\t\tExample: "For example: The first line contains N space-separated integers, denoting the elements of the array A[i]."
\t7. Sample Input:
\t\t~Header: Sample Input
\t\t~Content: Raw input values only — numbers/strings exactly as given. Each distinct variable gets its own line with "-- denotes {variable_name}" at the end. If multiple values belong to the same variable (e.g. all elements of an array), they must appear space-separated on a single line with ONE "-- denotes {variable_name}" at the end.
Example (single array): -2 1 -3 4 -1 2 1 -5 4    -- denotes arr
Example (two variables):
5            -- denotes N
abcda    -- denotes S
\t8. Constraints:
\t\t~Header: Constraints
\t\t~Content: Must be in range format (e.g., 1 < N < 100). Must NOT be written as prose/theory sentences.
        ~Required: Always present. If missing, flag as a Technical Mistake.
\t9. Output Format:
\t\t~Header: Output Format
\t\t~Content: definition of output type (int/string/array) followed by the main question part.
\t10. Sample Output:
\t\t~Header: Sample Output
\t\t~Content: The expected result.
\t11. Explanation:
\t\t~Header: Explanation
\t\t~Start: Must start with the word "Given".
\t\t~Format: "Given [variable definitions]..." (e.g., Given an array A[i] = [...]).
\t\t~End: The very last line must be: "Hence, the output is [X]." (Where X matches Sample Output)
\t\t~Math: ^ means exponentiation (raise to power). Do NOT flag or alter ^ expressions.

4. INSTRUCTIONS FOR PROCESSING
\t-Read the input text.
\t-Grammar Check: Scan the Problem Statement and Explanation for spelling or grammatical errors. Categorize these as Grammar Mistakes.
\t-Check the Sequence: Are sections in the 1-11 order?
\t-Check Headers: Are the headers (Note, Function Description, etc.) present.
\t-Check Title & Problem Statement: Ensure NO headers are used for these
\t-Check Explanation Logic: Ensure it starts with "Given" and ends with "Hence, the output is...".
\t-Check Data Types: Scan for Arrays and Strings and ensure they match the format A[i] = [...] and S = "...".
\t-Categorize any errors found while performing the above checks as Technical Mistakes.

5. STRICT ERROR CLASSIFICATION RULES (MANDATORY)
A. Grammar Mistakes MUST ONLY include:
   - Spelling errors
   - Typos
   - Incorrect punctuation, including a Problem Statement that ends with a question mark (?) instead of a period (.)
   - Subject-verb agreement errors
   - Awkward or unclear sentence construction
   - Incorrect tense or article usage

B. Grammar Mistakes MUST NOT include:
   - Missing or incorrect section headers
   - Incorrect header names (e.g., "NOTE" vs "Note")
   - Incorrect section order
   - Missing sections
   - Extra sections
   - Formatting violations
   - Template mismatches
   - Structural or organizational issues

C. Technical Mistakes MUST include:
   - Missing required sections (do NOT include optional sections)
   - Incorrect section order
   - Incorrect or extra headers
   - Header capitalization issues
   - Violation of the Function Description boilerplate template
   - Explanation not starting with "Given"
   - Explanation not ending with "Hence, the output is X."
   - Incorrect array or string formatting
   - Input/Output/Constraints format violations
   - Constraints written as prose/theory instead of range format
   - Sample Input lines missing the "-- denotes {variable_name}" annotation, or containing labels/descriptions beyond the raw value and its denotation
   - Note section present but was NOT in the original question
   - Multiple constraints written on the same line instead of each on its own separate line
   - Missing Constraints section (Constraints must always be present, even if not in the original — flag its absence as an error)

D. If an issue can be classified as BOTH Grammar and Technical,
   it MUST be classified as a Technical Mistake.

6. OUTPUT TEMPLATE
If errors are found, output the following format:
\"\"\"Grammar Mistakes: [GRAMMATICAL_MISTAKES]
Technical Mistakes: [TECHNICAL_MISTAKES]\"\"\"
If NO errors are found, output the following format:
\"\"\"Grammar Mistakes: No issues found.
Technical Mistakes: No issues found\"\"\"
All the errors stated MUST BE IN A PROPER ORDER OR LIST. in both Technical and Grammar Mistakes, each error should be on a new line."""

MISTAKE_FIXER_PROMPT = """Role: You are an Expert Technical Editor and Content Standardizer.
Objective: You will receive a Coding Question and an Error Report (Grammatical and Technical mistakes). Your task is to fix ONLY the reported errors while keeping everything else exactly as-is. You are a proofreader, NOT a rewriter.

CARDINAL RULES — NEVER VIOLATE THESE
1. NEVER change the Title. Copy it character-for-character from the original.
2. NEVER rewrite, shorten, summarize, or paraphrase the Problem Statement. Fix only the specific grammar errors listed. Every sentence of the original must be preserved.
3. NEVER add a Note section unless the original question already contained one.
4. NEVER add a phrase like "The goal is to...", "The objective is to...", or any introductory sentence not present in the original.
5. NEVER convert Constraints into prose/theory sentences. Constraints must stay in range format exactly (e.g., 1 ≤ N ≤ 10^5). Do not expand them into English sentences.
6. Each distinct variable in the Sample Input gets its own line with "-- denotes {variable_name}" at the end. If multiple values belong to the same variable (e.g. all elements of an array), they must be space-separated on a single line with ONE "-- denotes {variable_name}" at the end — never split across multiple lines. If the original is missing these annotations, ADD them based on the Input Format section.
7. NEVER interpret ^ as multiplication. ^ always means "raised to the power of" (exponentiation). Preserve all ^ expressions exactly as written. Do NOT change X^2Y to X*2*Y or any other form.
8. NEVER change numerical values, formulas, or computed results in the Explanation. Only fix grammar/formatting issues explicitly listed in the error report.
9. Always insert a blank line between the Title and the Problem Statement.
10. NEVER interpret * as markdown formatting. In the Explanation section, * always means multiplication. Preserve all * expressions exactly as written (e.g., 2*2*3*3*5*5 must stay as 2*2*3*3*5*5).

STYLE & FORMATTING GUIDE (The Source of Truth)
1. Global Formatting Rules
\t-Array Formatting: Convert all arrays to this format: A[i] = [1, 3, 5, 8]. Exception: In the Sample Input section, arrays must be written as raw space-separated values only (e.g., -2 1 -3 4 -1 2 1 -5 4 -- denotes arr). Never use A[i] = [...] format in Sample Input.
\t-String Formatting: Convert all strings to this format: S = "abc".
2. Section Sequence & Content Requirements
\t-You must structure the output in this exact order:
\t1. Title:
\t\t~Format: Bold and Italic only.
\t\t~Rule: Remove any "Title" headers. Copy the title text EXACTLY from the original — do not alter a single word. If no title is present, only THEN you must create a title based on the question.
\t\t~After the title, insert one blank line before the Problem Statement.
\t2. Problem Statement:
\t\t~Format: Standard text.
\t\t~Rule: Remove any "Problem Statement" headers.
\t\t~Rule: Preserve every sentence of the original Problem Statement. Do NOT summarize, shorten, or add new sentences.
\t\t~~Ending: Must end with the main task/objective. It must end with a period (.), never a question mark (?).
\t3. Note: (Include ONLY if present in original input — if absent in original, do NOT create one)
\t\t~Header: Note
\t4. Example: (Include only if present in original input)
\t\t~Header: Example
\t5. Function Description:
\t\t~Header: Function Description
\t\t~Rule: Replace the original text with this EXACT boilerplate (fill in the bracketed placeholders based on the question context):
"In the provided code snippet, implement the provided [FUNCTION_NAME] method using the variables to print the [TASK_DESCRIPTION]. You can write your code in the space below the phrase "WRITE YOUR LOGIC HERE". There will be multiple test cases running so the Input and Output should match exactly as provided. The base Output variable result is set to a default value of -404 which can be modified. Additionally, you can add or remove these output variables."
\t6. Input Format:
\t\t~Header: Input Format
\t7. Sample Input:
\t\t~Header: Sample Input
\t\t~Rule: Each distinct variable gets its own line. If multiple values belong to the same variable (e.g. array elements), keep them space-separated on ONE line with a single "-- denotes {variable_name}" at the end. Derive variable names from the Input Format section if not present in the original.
Example (single array): -2 1 -3 4 -1 2 1 -5 4  -- denotes arr
Example (two variables):
5  -- denotes N
abcda  -- denotes S
        ~Rule: Do NOT add any other labels or descriptions beyond this format.
        ~Rule: Never apply array initialization format (A[i] = [...]) here. Raw values only.
\t8. Constraints:
\t\t~Header: Constraints
\t\t~Rule: Copy constraints EXACTLY in their original range format (e.g., 1 ≤ N ≤ 10^5). Do NOT convert to prose sentences. Do NOT add a Note section to hold constraint information.
        ~Rule: Each constraint must be on its own separate line. Never write multiple constraints on the same line.
        ~Rule: If the original question does not have a Constraints section, you MUST infer and add one based on the variable types and context of the problem (e.g., array size, value ranges, string length). Constraints must always be present in the final output.
\t9. Output Format:
\t\t~Header: Output Format
\t10. Sample Output:
\t\t~Header: Sample Output
\t11. Explanation:
\t\t~Header: Explanation
\t\t~Start: Rewrite the start to begin with "Given [variables]...".
\t\t~End: Rewrite the final line to be exactly: "Hence, the output is [X]." (Ensure X matches the Sample Output)
\t\t~Math Rule: ^ means exponentiation (raise to the power). NEVER change ^ to * or expand it. Preserve all formulas (e.g., X^2Y stays as X^2Y) and all calculated numeric values exactly.

INSTRUCTIONS FOR PROCESSING
1. Analyze the Inputs: Read the Original Question and the Technical and Grammatical Mistakes.
2. Fix Grammar: Correct ONLY the specific spelling, typo, and punctuation errors listed in "Grammatical Mistakes". Do not touch anything else in the Problem Statement.
3. Fix Technical Structure: Reorder the sections and apply the headers exactly as defined in the Guide.
4. Fix Boilerplate: Inject the correct Function Description boilerplate.
5. Fix Explanation Format: Reword only the opening to start with "Given" and only the closing to end with "Hence, the output is...". Keep all calculations and values untouched.
6. Fix Array/String Formatting: Reformat Arrays (A[i] = [...]) and Strings (S = "...") wherever they appear.
7. Sanity Check: Ensure the math/logic of the question (input values vs output values) remains completely unchanged.

OUTPUT FORMAT
Output ONLY the fully corrected, final version of the question. Do not include any chat or conversational filler."""


# ─────────────────────────────────────────────
# JS → Python logic (your two Code nodes)
# ─────────────────────────────────────────────
def split_mistakes(text: str) -> tuple[str, str]:
    """Mirrors 'Code in JavaScript' node: splits LLM output into grammar/technical."""
    parts = re.split(r'\n\s*Technical Mistakes:', text, flags=re.IGNORECASE)
    grammar = parts[0].replace('Grammar Mistakes:', '').strip()
    technical = parts[1].strip() if len(parts) > 1 else ''
    return grammar, technical


def normalize_headers(text: str) -> str:
    """Mirrors 'Code in JavaScript1' node: normalises section headers."""
    # Unescape literal \n sequences
    cleaned = text.replace('\\\\n', '\n').replace('\\n', '\n')

    headers = [
        'Note', 'Example', 'Function Description', 'Input Format',
        'Sample Input', 'Constraints', 'Output Format', 'Sample Output', 'Explanation'
    ]
    for header in headers:
        pattern = re.compile(
            rf'(^|\n)(#{"{1,6}"}\s*)?(__)?(\*{{0,2}}){re.escape(header)}(\*{{0,2}})(__)?(\s*)',
            re.IGNORECASE
        )
        cleaned = pattern.sub(f'\n\n**{header}**\n', cleaned)

    return cleaned


# ─────────────────────────────────────────────
# Core pipeline
# ─────────────────────────────────────────────
def run_pipeline(question: str) -> dict:
    if not GROQ_API_KEY_VALIDATOR or not GROQ_API_KEY_FIXER:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY_VALIDATOR and GROQ_API_KEY_FIXER must both be set.")

    # Step 1 — Find mistakes (Basic LLM Chain)
    logger.info("Step 1: Finding mistakes...")
    resp1 = client_validator.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": MISTAKE_FINDER_PROMPT},
            {"role": "user",   "content": question},
        ],
    )
    mistakes_text = resp1.choices[0].message.content

    # Step 2 — Split grammar / technical (Code in JavaScript)
    grammar_mistakes, technical_mistakes = split_mistakes(mistakes_text)

    # Step 3 — Fix mistakes (change mistakes chain)
    logger.info("Step 2: Fixing mistakes...")
    fix_prompt = (
        f'Original Question "{question}"\n'
        f'Grammatical Mistakes: "{grammar_mistakes}"\n'
        f'Technical Mistakes: "{technical_mistakes}"'
    )
    resp2 = client_fixer.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": MISTAKE_FIXER_PROMPT},
            {"role": "user",   "content": fix_prompt},
        ],
    )
    fixed_text = resp2.choices[0].message.content

    # Step 4 — Normalize headers (Code in JavaScript1)
    formatted_question = normalize_headers(fixed_text)

    return {
        "grammarMistakes":   grammar_mistakes,
        "technicalMistakes": technical_mistakes,
        "formattedQuestion": formatted_question,
    }


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────
class TextRequest(BaseModel):
    question: str


@app.post("/proofread")
async def proofread_text(body: TextRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question text is required.")
    return run_pipeline(body.question)


@app.post("/proofread-file")
async def proofread_file(file: UploadFile = File(...)):
    MAX_SIZE = 2 * 1024 * 1024  # 2 MB
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max 2 MB.")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text.")
    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty.")
    return run_pipeline(text)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────
# Serve the frontend (static HTML)
# ─────────────────────────────────────────────
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
