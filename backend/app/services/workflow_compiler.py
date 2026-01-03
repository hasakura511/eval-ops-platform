"""
Workflow Compiler Service

Parses evaluation guidelines into structured workflows with:
- Explicit steps
- Required artifacts
- Verification rules
- Evidence gates
"""

import re
from typing import List, Dict, Any, Tuple
from app.schemas.schemas import WorkflowStep, ArtifactType, TaskType
import uuid


class WorkflowCompiler:
    """Compiles evaluation guidelines into executable workflows."""
    
    # Keywords that indicate required steps
    STEP_KEYWORDS = {
        'verify': ['verify', 'check', 'confirm', 'validate', 'ensure'],
        'capture': ['screenshot', 'capture', 'save', 'record', 'snapshot'],
        'extract': ['extract', 'identify', 'find', 'locate', 'read'],
        'compare': ['compare', 'match', 'cross-reference', 'contrast'],
        'rate': ['rate', 'score', 'evaluate', 'assess', 'judge']
    }
    
    # Evidence requirement patterns
    EVIDENCE_PATTERNS = [
        r'must (?:include|provide|show|demonstrate)',
        r'required to (?:include|provide|show)',
        r'(?:screenshot|image|photo) (?:of|showing|at)',
        r'(?:cite|reference|link to)',
        r'cannot (?:verify|confirm) without'
    ]
    
    # Banned phrase patterns
    BANNED_PHRASE_INDICATORS = [
        r'do not (?:use|say|include)',
        r'avoid (?:using|saying|claiming)',
        r'never (?:use|say|claim)',
        r'prohibited (?:terms|phrases|language)'
    ]
    
    def compile(
        self, 
        guideline_text: str, 
        workflow_name: str,
        task_type: TaskType
    ) -> Tuple[List[WorkflowStep], Dict[str, Any], List[str]]:
        """
        Compile guidelines into workflow steps.
        
        Returns:
            (steps, verifier_rules, banned_phrases)
        """
        # Parse into sections
        sections = self._parse_sections(guideline_text)
        
        # Extract steps from guidelines
        steps = self._extract_steps(sections, task_type)
        
        # Extract verifier rules
        verifier_rules = self._extract_verifier_rules(sections)
        
        # Extract banned phrases
        banned_phrases = self._extract_banned_phrases(sections)
        
        return steps, verifier_rules, banned_phrases
    
    def _parse_sections(self, text: str) -> List[Dict[str, str]]:
        """Parse guideline text into sections."""
        sections = []
        
        # Split by headers (markdown-style or numbered)
        header_pattern = r'^#+\s+(.+)|^\d+\.\s+(.+)|^([A-Z][^.!?]*):$'
        
        current_section = None
        current_content = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            header_match = re.match(header_pattern, line, re.MULTILINE)
            if header_match:
                if current_section:
                    sections.append({
                        'header': current_section,
                        'content': '\n'.join(current_content)
                    })
                current_section = next(g for g in header_match.groups() if g)
                current_content = []
            else:
                current_content.append(line)
        
        # Add last section
        if current_section:
            sections.append({
                'header': current_section,
                'content': '\n'.join(current_content)
            })
        
        return sections
    
    def _extract_steps(
        self, 
        sections: List[Dict[str, str]], 
        task_type: TaskType
    ) -> List[WorkflowStep]:
        """Extract workflow steps from sections."""
        steps = []
        
        # Default step templates based on task type
        if task_type == TaskType.VERIFY:
            steps.extend([
                WorkflowStep(
                    step_id=str(uuid.uuid4()),
                    type="capture",
                    produces=ArtifactType.SCREENSHOT,
                    verifiers=["screenshot_required"]
                ),
                WorkflowStep(
                    step_id=str(uuid.uuid4()),
                    type="extract",
                    requires=["capture"],
                    produces=ArtifactType.OBSERVATION_LEDGER,
                    verifiers=["ledger_complete"]
                ),
                WorkflowStep(
                    step_id=str(uuid.uuid4()),
                    type="rate",
                    requires=["extract"],
                    produces=ArtifactType.DECISION,
                    verifiers=["evidence_gated_decision"]
                )
            ])
        
        elif task_type == TaskType.COMPARE:
            steps.extend([
                WorkflowStep(
                    step_id=str(uuid.uuid4()),
                    type="extract",
                    produces=ArtifactType.EVIDENCE_PACK,
                    verifiers=["citations_required"]
                ),
                WorkflowStep(
                    step_id=str(uuid.uuid4()),
                    type="compare",
                    requires=["extract"],
                    produces=ArtifactType.DIFF,
                    verifiers=["diff_complete"]
                ),
                WorkflowStep(
                    step_id=str(uuid.uuid4()),
                    type="rate",
                    requires=["compare"],
                    produces=ArtifactType.DECISION,
                    verifiers=["evidence_gated_decision"]
                )
            ])
        
        else:
            # Generic extraction + rating
            steps.extend([
                WorkflowStep(
                    step_id=str(uuid.uuid4()),
                    type="extract",
                    produces=ArtifactType.EVIDENCE_PACK,
                    verifiers=["evidence_required"]
                ),
                WorkflowStep(
                    step_id=str(uuid.uuid4()),
                    type="rate",
                    requires=["extract"],
                    produces=ArtifactType.DECISION,
                    verifiers=["evidence_gated_decision"]
                )
            ])
        
        # Augment with guideline-specific requirements
        for section in sections:
            content_lower = section['content'].lower()
            
            # Check for screenshot requirements
            if any(kw in content_lower for kw in ['screenshot', 'zoom', 'satellite', 'image']):
                # Add screenshot step if not present
                has_screenshot = any(s.type == "capture" for s in steps)
                if not has_screenshot:
                    steps.insert(0, WorkflowStep(
                        step_id=str(uuid.uuid4()),
                        type="capture",
                        produces=ArtifactType.SCREENSHOT,
                        verifiers=["screenshot_required"]
                    ))
        
        return steps
    
    def _extract_verifier_rules(
        self, 
        sections: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Extract verifier rules from guidelines."""
        rules = {
            'required_artifacts': [],
            'citation_requirements': {},
            'field_requirements': [],
            'custom_checks': []
        }
        
        for section in sections:
            content = section['content']
            
            # Check for evidence patterns
            for pattern in self.EVIDENCE_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    # Extract what's required
                    match = re.search(pattern + r'\s+(.+?)(?:\.|$)', content, re.IGNORECASE)
                    if match:
                        requirement = match.group(1).strip()
                        rules['required_artifacts'].append(requirement)
            
            # Check for field requirements (e.g., "must include: X, Y, Z")
            field_pattern = r'must include:\s*(.+?)(?:\n|$)'
            field_match = re.search(field_pattern, content, re.IGNORECASE)
            if field_match:
                fields = [f.strip() for f in field_match.group(1).split(',')]
                rules['field_requirements'].extend(fields)
            
            # Citation requirements
            if 'citation' in content.lower() or 'source' in content.lower():
                citation_pattern = r'(?:at least|minimum of|≥)\s*(\d+)\s*(?:citations?|sources?)'
                citation_match = re.search(citation_pattern, content, re.IGNORECASE)
                if citation_match:
                    rules['citation_requirements']['min_count'] = int(citation_match.group(1))
        
        return rules
    
    def _extract_banned_phrases(
        self, 
        sections: List[Dict[str, str]]
    ) -> List[str]:
        """Extract banned phrases from guidelines."""
        banned = []
        
        for section in sections:
            content = section['content']
            
            for pattern in self.BANNED_PHRASE_INDICATORS:
                matches = re.finditer(pattern + r'\s*[:\"]?\s*(.+?)(?:\"|\.|\n|$)', content, re.IGNORECASE)
                for match in matches:
                    phrase = match.group(1).strip()
                    # Split on common delimiters
                    phrases = re.split(r'[,;]|\sand\s|\sor\s', phrase)
                    banned.extend([p.strip().strip('"\'') for p in phrases if p.strip()])
        
        return list(set(banned))


def compile_workflow_from_guideline(
    workspace_id: str,
    guideline_text: str,
    workflow_name: str,
    task_type: TaskType
) -> Dict[str, Any]:
    """
    High-level function to compile a workflow from guideline text.
    
    Returns workflow data ready for database insertion.
    """
    compiler = WorkflowCompiler()
    
    steps, verifier_rules, banned_phrases = compiler.compile(
        guideline_text, 
        workflow_name,
        task_type
    )
    
    # Convert steps to dict format
    steps_dict = [
        {
            'step_id': step.step_id,
            'type': step.type,
            'requires': step.requires,
            'produces': step.produces.value,
            'verifiers': step.verifiers
        }
        for step in steps
    ]
    
    return {
        'workspace_id': workspace_id,
        'name': workflow_name,
        'steps': steps_dict,
        'retry_policy': {'max_retries': 2, 'backoff': 'exponential'},
        'escalation_rules': {
            'failed_verifications': 'require_human_review',
            'low_confidence': 'flag_for_adjudication'
        },
        'compiled_from': guideline_text,
        'verifier_rules': verifier_rules,
        'banned_phrases': banned_phrases
    }
