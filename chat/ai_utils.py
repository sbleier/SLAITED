import os
from openai import OpenAI
from dotenv import load_dotenv

# ============================================================================
# SYSTEM PROMPT - Core AI Behavior
# ============================================================================

SLAITED_SYSTEM_PROMPT = """
You are a Socratic dialogue partner guiding secondary students through historical thinking.

Your role is to guide student thinking through questions, not to explain history or summarize sources.
You enforce ONE historical thinking skill at a time.

CORE CONSTRAINTS
- Ask ONLY one question per response.
- Use at most 2 short sentences.
- Do NOT summarize or describe the source.
- Do NOT answer the guiding question for the student.
- Do NOT move to another skill unless instructed by the session state
- DO prompt the student to click 'Continue' when they've demonstrated understanding.

SOCRATIC METHOD
- Every question must build directly on the student’s last response.
- If a student response is vague, ask for specificity from the source.
- If the student shifts to a different skill, redirect them back to the current skill.

PREREQUISITE KNOWLEDGE RULE
- If the student cannot reasonably answer a question for the current skill
  because they lack necessary background knowledge that is not provided in the source,
    • You MAY provide up to 1–2 brief factual statements from the historical context.
    • Do NOT explain or interpret the source.
    • Immediately follow with ONE question that requires the student to use that information.

USE OF HISTORICAL CONTEXT
- Historical context is used only to support student thinking.
- Do not replace reading, interpretation, or reasoning with explanation.
- Do not assume the publication year is the same as the time of events described.

SKILL DISCIPLINE
- You are enforcing ONE cognitive move at a time.
- If a question would require a different skill, do not ask it.
- If the student asks something outside the skill:
  “Let’s stay focused on [current skill] with this source.”
- Once the student demonstrates mastery for the current skill, do NOT ask further questions. 
- Do not repeat questions about points already answered.

IMPORTANT: Follow the specific guidance and constraints in the references for the current skill exactly.

EVALUATION BEHAVIOR
- Affirm only when the student demonstrates the current skill.
- If the skill is not yet demonstrated, ask ONE focused follow-up question.
- Avoid praise for unsupported or vague answers.

Your goal is to keep the student thinking, not to think for them.
"""

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ============================================================================
# REFERENCE MATERIAL LOADERS
# ============================================================================

def load_skills_reference():
    """Load skill definitions from reference file."""
    file_path = os.path.join(os.path.dirname(__file__), 'reference_materials', 'historical_thinking_skills.txt')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""


def load_historical_context():
    """Load historical context information from reference file."""
    file_path = os.path.join(os.path.dirname(__file__), 'reference_materials', 'historical_context.txt')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""


# ============================================================================
# MODEL CALLING
# ============================================================================

def call_model(messages_history, include_skills=True, include_context=False, session_context=None):
    """
    Call the AI model with full conversation history and reference materials.
    Ensures that references are explicitly used and cannot be ignored.
    Args:
        messages_history: List of conversation messages (user/assistant alternating)
        include_skills: Include skill definitions reference
        include_context: Include historical context reference
        session_context: String with current session state (phase, source, skill, etc.)

    Returns:
        AI response as string
    """
    system_content = SLAITED_SYSTEM_PROMPT

    # Add explicit instruction to use references
    instructions = "\n\n===== REFERENCE MATERIAL USAGE =====\n"
    instructions += "You MUST use the following reference materials when generating questions or evaluating student responses. Do NOT ignore them.\n"

    # Add skill definitions if requested
    if include_skills:
        skills_ref = load_skills_reference()
        if skills_ref:
            instructions += "\n" + "="*60 + "\n"
            instructions += "HISTORICAL THINKING SKILLS REFERENCE\n"
            instructions += "="*60 + "\n"
            instructions += skills_ref

    # Add historical context if requested
    if include_context:
        context_ref = load_historical_context()
        if context_ref:
            instructions += "\n" + "="*60 + "\n"
            instructions += "HISTORICAL CONTEXT REFERENCE\n"
            instructions += "="*60 + "\n"
            instructions += context_ref

    system_content += instructions
    # Add current session state
    if session_context:
        system_content += "\n\n" + "="*60 + "\n"
        system_content += "CURRENT SESSION STATE\n"
        system_content += "\n\n" + "="*60 + "\n"
        system_content += session_context

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": system_content}] + messages_history,
        temperature=0.7
    )
    return response.choices[0].message.content


# ============================================================================
# SKILL MASTERY EVALUATION
# ============================================================================

def evaluate_skill_mastery(skill, proficiency, evidence, conversation_excerpt=None):
    """
    Evaluate if student has demonstrated mastery of a skill.

    Args:
        skill: The historical thinking skill being evaluated
        proficiency: Student's proficiency level (beginner/intermediate/advanced)
        evidence: List of student responses for this skill
        conversation_excerpt: Optional - recent Q&A pairs for better context

    Returns:
        Dict with mastery status and reasoning
    """
    if not evidence:
        return {
            "is_mastered": False,
            "reasoning": "No evidence yet - student hasn't engaged with the skill."
        }

    evidence_text = "\n".join(f"Response {i+1}: {e}" for i, e in enumerate(evidence))

    conversation_context = ""
    if conversation_excerpt:
        conversation_context = f"\n\nRecent conversation (shows what questions were asked):\n{conversation_excerpt}"

    # Adjust criteria based on proficiency level
    if proficiency == "beginner":
        criteria_description = """
For BEGINNERS, mastery means:
- About 2-3 responses that show basic understanding
- Student addresses the skill at a basic level (doesn't need to be sophisticated)
- Shows genuine engagement with the source (even if answers are simple)
- Quality bar should be LOW - we want to encourage progress, not perfection
"""
    elif proficiency == "intermediate":
        criteria_description = """
For INTERMEDIATE students, mastery means:
- 3-4 substantive responses showing solid understanding
- Student clearly addresses the target skill with some depth
- Shows direct engagement with specific details in the source
"""
    else:  # advanced
        criteria_description = """
For ADVANCED students, mastery means:
- 4-5 sophisticated responses showing deep understanding
- Student demonstrates nuanced grasp of the skill
- Makes connections and shows critical thinking
"""

    prompt = f"""
You are evaluating whether a student has demonstrated a historical thinking skill.

Skill: {skill}
Student proficiency level: {proficiency}

{criteria_description}

Student responses during this skill:
{evidence_text}{conversation_context}

IMPORTANT: 
- Look at the conversation context to see if the student actually ANSWERED the questions asked
- Evaluate based on what the '{skill}' skill requires (as defined in historical thinking skills)
- Don't just count responses - evaluate if they engaged meaningfully with the skill
- Be generous with beginners - if they're trying and showing basic understanding, let them advance

Respond in JSON format:
{{
    "is_mastered": true/false,
    "reasoning": "brief explanation of what the student did well or what's missing"
}}
"""

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"}
    )

    import json
    result = json.loads(response.choices[0].message.content)
    return result


# ============================================================================
# CONVERSATION HISTORY BUILDING
# ============================================================================

def build_conversation_history(session, limit_to_current_skill=False):
    """
    Build conversation history from the database.

    Args:
        session: The current session
        limit_to_current_skill: If True, only return messages from current source+skill start.
                               If False, return entire session history.

    Returns:
        List of message dicts in OpenAI format [{"role": "user"/"assistant", "content": "..."}]
    """
    from .models import Message

    messages = Message.objects.filter(session=session).order_by('created_at')

    # If we want to limit to current skill, find where it started
    if limit_to_current_skill and session.session_data.get("current_phase") == "source_loop":
        source_index = session.session_data.get("source_index", 0)
        skill_index = session.session_data.get("skill_index", 0)

        # Find the message where this skill was introduced (phase transition with no user message)
        skill_start_index = None
        for i, msg in enumerate(messages):
            msg_phase = msg.request.get('phase', '')
            msg_user_content = msg.request.get('message')
            msg_source_idx = msg.request.get('source_index')
            msg_skill_idx = msg.request.get('skill_index')

            # Look for phase transition that matches our current indices
            if (msg_phase == 'source_loop' and
                    msg_user_content is None and
                    msg_source_idx == source_index and
                    msg_skill_idx == skill_index):
                skill_start_index = i
                break

        # If we found the start, slice from there
        if skill_start_index is not None:
            messages = messages[skill_start_index:]

    # Build OpenAI-formatted message list
    history = []
    for msg in messages:
        user_content = msg.request.get('message')
        if user_content:
            history.append({
                "role": "user",
                "content": user_content
            })

        assistant_content = msg.response.get('message')
        if assistant_content:
            history.append({
                "role": "assistant",
                "content": assistant_content
            })

    return history


# ============================================================================
# SESSION STATE HELPERS
# ============================================================================

def should_include_context(skill):
    """Determine if historical context should be included based on skill."""
    skill_lower = skill.lower()
    # Context is helpful for contextualization and sourcing skills
    return 'context' in skill_lower or 'sourcing' in skill_lower


def build_session_context(session, is_phase_transition=False):
    """
    Build a formatted string describing the current session state.
    This goes into the system prompt to orient the AI.

    Args:
        session: StudentInteractionSession instance
        is_phase_transition: If True, we're introducing a NEW phase/skill (not continuing conversation)

    Returns:
        Formatted string with session state information
    """
    phase = session.session_data.get("current_phase", "intro")
    assignment = session.assignment
    requirement = assignment.requirement

    lines = [
        f"Topic: {requirement.topic}",
        f"Guiding Question: {requirement.guiding_question}",
        f"Student Proficiency: {requirement.student_proficiency}",
        f"Current Phase: {phase}",
    ]

    if phase == "intro":
        lines.append("\n[INTRO PHASE GUIDANCE]")
        lines.append("Welcome the student warmly and introduce yourself as their AI guide.")
        lines.append("Mention the guiding question they'll explore.")
        lines.append("Keep it brief and friendly - they'll click 'Ready to Begin' when ready.")

    elif phase == "source_loop":
        sources = assignment.sources
        skills = requirement.skills_to_target

        source_index = session.session_data.get("source_index", 0)
        skill_index = session.session_data.get("skill_index", 0)

        if source_index >= len(sources):
            lines.append("\n[ALL SOURCES COMPLETE]")
            lines.append("The student has completed all sources. Congratulate them!")
            return "\n".join(lines)

        if skill_index >= len(skills):
            lines.append("\n[ERROR: Skill index out of bounds]")
            return "\n".join(lines)

        current_source = sources[source_index]
        current_skill = skills[skill_index]

        lines.append(f"\n[CURRENT TASK]")
        lines.append(f"Source: {source_index + 1} of {len(sources)}")
        lines.append(f"Skill: {current_skill} (skill {skill_index + 1} of {len(skills)})")
        lines.append(f"\nSource Information:")
        lines.append(f"  Title: {current_source.get('title', 'Untitled')}")
        lines.append(f"  Author: {current_source.get('author', 'Unknown')}")
        lines.append(f"  Year: {current_source.get('year', 'n.d.')}")
        lines.append(f"\nSource Text:")
        lines.append(f'  "{current_source.get("text", "")}"')

        lines.append(f"\n[YOUR TASK]")
        if is_phase_transition:
            if skill_index == 0:
                lines.append(f"You are introducing a NEW source: Source {source_index + 1}.")
                lines.append(f"Present the source metadata (title, author, year) and ask the student to read the source.")
            else:
                lines.append(f"You are introducing a new skill '{current_skill}' for the current source.: {source_index + 1}")
            #lines.append(f"Then follow the Guidance Rules for '{current_skill}' step by step.")
           # lines.append(f"Respect the Constraints - they define what NOT to do for this skill.")
        else:
            lines.append(f"Continue guiding through '{current_skill}'.")
            #lines.append(f"Follow the Guidance Rules and respect the Constraints.")
            q_count = session.session_data.get("questions_asked_this_skill", 0)
            lines.append(f"Questions asked so far for this skill: {q_count}")
            if q_count >= 4:
                lines.append(
                    "IMPORTANT: The student has likely demonstrated this skill."
                )
                lines.append(
                    "Your task now is to acknowledge their effort briefly."
                )
                lines.append(
                    "If needed, ask AT MOST ONE final, narrow question that can be answered in one sentence."
                )
                lines.append(
                    "Otherwise, tell them they may click Continue."
                )

        lines.append(f"The student will click 'Continue' when ready to move to the next skill.")


    return "\n".join(lines)


def get_recent_conversation_excerpt(session, num_exchanges=3):
    """
    Get the last N question-answer exchanges for context.
    Used in skill mastery evaluation to show what questions were asked.

    Args:
        session: StudentInteractionSession instance
        num_exchanges: Number of recent Q&A pairs to include

    Returns:
        Formatted string with recent conversation
    """
    from .models import Message

    messages = Message.objects.filter(session=session).order_by('-created_at')[:num_exchanges * 2]
    messages = list(reversed(messages))  # Put back in chronological order

    excerpt_parts = []
    for msg in messages:
        user_msg = msg.request.get('message')
        ai_msg = msg.response.get('message')

        if ai_msg:
            excerpt_parts.append(f"AI: {ai_msg}")
        if user_msg:
            excerpt_parts.append(f"Student: {user_msg}")

    return "\n".join(excerpt_parts) if excerpt_parts else None