"""
Verifier Engine

Enforces evidence-gated decisions and prevents "simulated verification."
Each verifier is a pluggable rule that checks artifacts and execution outputs.
"""

from typing import List, Dict, Any, Optional
from app.schemas.schemas import ArtifactType
import re


class VerificationViolation:
    """Represents a single verification failure."""
    def __init__(self, rule: str, field: str, reason: str, evidence: Any = None):
        self.rule = rule
        self.field = field
        self.reason = reason
        self.evidence = evidence
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'rule': self.rule,
            'field': self.field,
            'reason': self.reason,
            'evidence': self.evidence
        }


class VerifierEngine:
    """Engine that runs verification rules against artifacts and executions."""
    
    def __init__(self):
        self.verifiers = {
            'screenshot_required': self._verify_screenshot_required,
            'ledger_complete': self._verify_ledger_complete,
            'evidence_required': self._verify_evidence_required,
            'citations_required': self._verify_citations_required,
            'evidence_gated_decision': self._verify_evidence_gated_decision,
            'banned_phrases': self._verify_banned_phrases,
            'required_fields': self._verify_required_fields,
            'diff_complete': self._verify_diff_complete,
            'screenshot_hash_valid': self._verify_screenshot_hash_valid,
            'artifact_referenced': self._verify_artifact_referenced,
            'observation_specificity': self._verify_observation_specificity
        }
    
    def verify(
        self,
        verifier_name: str,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        rule_config: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, List[VerificationViolation]]:
        """
        Run a verifier.
        
        Returns:
            (passed, violations)
        """
        if verifier_name not in self.verifiers:
            raise ValueError(f"Unknown verifier: {verifier_name}")
        
        violations = self.verifiers[verifier_name](
            artifacts, 
            execution, 
            rule_config or {}
        )
        
        return len(violations) == 0, violations
    
    # ============================================================================
    # VERIFIER IMPLEMENTATIONS
    # ============================================================================
    
    def _verify_screenshot_required(
        self,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[VerificationViolation]:
        """Verify that a screenshot artifact exists."""
        violations = []
        
        screenshots = [a for a in artifacts if a.get('artifact_type') == ArtifactType.SCREENSHOT.value]
        
        if not screenshots:
            violations.append(VerificationViolation(
                rule='screenshot_required',
                field='artifacts',
                reason='No screenshot artifact found'
            ))
        
        return violations
    
    def _verify_ledger_complete(
        self,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[VerificationViolation]:
        """Verify observation ledger has required structure."""
        violations = []
        
        ledgers = [a for a in artifacts if a.get('artifact_type') == ArtifactType.OBSERVATION_LEDGER.value]
        
        if not ledgers:
            violations.append(VerificationViolation(
                rule='ledger_complete',
                field='artifacts',
                reason='No observation ledger found'
            ))
            return violations
        
        ledger = ledgers[0]
        data = ledger.get('data', {})
        
        # Required fields in ledger
        required = ['observations', 'cannot_verify']
        for field in required:
            if field not in data:
                violations.append(VerificationViolation(
                    rule='ledger_complete',
                    field=field,
                    reason=f'Ledger missing required field: {field}'
                ))
        
        # Must have at least one observation or cannot_verify entry
        if not data.get('observations') and not data.get('cannot_verify'):
            violations.append(VerificationViolation(
                rule='ledger_complete',
                field='content',
                reason='Ledger must contain at least one observation or cannot_verify entry'
            ))
        
        return violations
    
    def _verify_evidence_required(
        self,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[VerificationViolation]:
        """Verify evidence pack exists and contains evidence."""
        violations = []
        
        evidence_packs = [a for a in artifacts if a.get('artifact_type') == ArtifactType.EVIDENCE_PACK.value]
        
        if not evidence_packs:
            violations.append(VerificationViolation(
                rule='evidence_required',
                field='artifacts',
                reason='No evidence pack found'
            ))
            return violations
        
        pack = evidence_packs[0]
        data = pack.get('data', {})
        
        if not data.get('evidence') and not data.get('snippets'):
            violations.append(VerificationViolation(
                rule='evidence_required',
                field='content',
                reason='Evidence pack is empty'
            ))
        
        return violations
    
    def _verify_citations_required(
        self,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[VerificationViolation]:
        """Verify citations meet requirements."""
        violations = []
        
        evidence_packs = [a for a in artifacts if a.get('artifact_type') == ArtifactType.EVIDENCE_PACK.value]
        
        if not evidence_packs:
            violations.append(VerificationViolation(
                rule='citations_required',
                field='artifacts',
                reason='No evidence pack for citations'
            ))
            return violations
        
        pack = evidence_packs[0]
        citations = pack.get('data', {}).get('citations', [])
        
        min_citations = config.get('min_count', 1)
        if len(citations) < min_citations:
            violations.append(VerificationViolation(
                rule='citations_required',
                field='citations',
                reason=f'Expected at least {min_citations} citations, found {len(citations)}',
                evidence={'found': len(citations), 'required': min_citations}
            ))
        
        # Verify citations map to source spans
        for i, citation in enumerate(citations):
            if not citation.get('source_id'):
                violations.append(VerificationViolation(
                    rule='citations_required',
                    field=f'citation[{i}]',
                    reason='Citation missing source_id'
                ))
            
            if not citation.get('text'):
                violations.append(VerificationViolation(
                    rule='citations_required',
                    field=f'citation[{i}]',
                    reason='Citation missing text content'
                ))
        
        return violations
    
    def _verify_evidence_gated_decision(
        self,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[VerificationViolation]:
        """Verify decision only references observed facts."""
        violations = []
        
        decision = execution.get('decision', {})
        
        if not decision:
            violations.append(VerificationViolation(
                rule='evidence_gated_decision',
                field='decision',
                reason='No decision found'
            ))
            return violations
        
        # Check rationale exists
        rationale = decision.get('rationale', '')
        if not rationale:
            violations.append(VerificationViolation(
                rule='evidence_gated_decision',
                field='rationale',
                reason='Decision missing rationale'
            ))
            return violations
        
        # Check that rationale references artifacts
        # Look for artifact IDs or references to ledger/evidence
        has_artifact_ref = any(
            a.get('id') in rationale 
            for a in artifacts
        )
        
        has_evidence_keywords = any(
            keyword in rationale.lower() 
            for keyword in ['observed', 'ledger', 'screenshot', 'evidence', 'verified']
        )
        
        if not has_artifact_ref and not has_evidence_keywords:
            violations.append(VerificationViolation(
                rule='evidence_gated_decision',
                field='rationale',
                reason='Rationale does not reference artifacts or evidence'
            ))
        
        return violations
    
    def _verify_banned_phrases(
        self,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[VerificationViolation]:
        """Verify no banned phrases appear in decision."""
        violations = []
        
        banned = config.get('phrases', [])
        if not banned:
            return violations
        
        decision = execution.get('decision', {})
        rationale = decision.get('rationale', '').lower()
        
        for phrase in banned:
            if phrase.lower() in rationale:
                violations.append(VerificationViolation(
                    rule='banned_phrases',
                    field='rationale',
                    reason=f'Banned phrase found: "{phrase}"',
                    evidence={'phrase': phrase}
                ))
        
        return violations
    
    def _verify_required_fields(
        self,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[VerificationViolation]:
        """Verify required fields are present in decision."""
        violations = []
        
        required_fields = config.get('fields', [])
        decision = execution.get('decision', {})
        
        for field in required_fields:
            if field not in decision or not decision[field]:
                violations.append(VerificationViolation(
                    rule='required_fields',
                    field=field,
                    reason=f'Required field missing or empty: {field}'
                ))
        
        return violations
    
    def _verify_diff_complete(
        self,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[VerificationViolation]:
        """Verify diff artifact has complete comparison."""
        violations = []
        
        diffs = [a for a in artifacts if a.get('artifact_type') == ArtifactType.DIFF.value]
        
        if not diffs:
            violations.append(VerificationViolation(
                rule='diff_complete',
                field='artifacts',
                reason='No diff artifact found'
            ))
            return violations
        
        diff = diffs[0]
        data = diff.get('data', {})
        
        required = ['before', 'after', 'changes']
        for field in required:
            if field not in data:
                violations.append(VerificationViolation(
                    rule='diff_complete',
                    field=field,
                    reason=f'Diff missing required field: {field}'
                ))
        
        return violations
    
    def _verify_screenshot_hash_valid(
        self,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[VerificationViolation]:
        """Verify screenshot has valid content hash."""
        violations = []
        
        screenshots = [a for a in artifacts if a.get('artifact_type') == ArtifactType.SCREENSHOT.value]
        
        for screenshot in screenshots:
            if not screenshot.get('content_hash'):
                violations.append(VerificationViolation(
                    rule='screenshot_hash_valid',
                    field='content_hash',
                    reason='Screenshot missing content hash',
                    evidence={'artifact_id': screenshot.get('id')}
                ))
            
            # Optionally verify hash format
            hash_val = screenshot.get('content_hash', '')
            if hash_val and not re.match(r'^[a-f0-9]{64}$', hash_val):
                violations.append(VerificationViolation(
                    rule='screenshot_hash_valid',
                    field='content_hash',
                    reason='Screenshot hash invalid format (expected SHA-256)',
                    evidence={'hash': hash_val}
                ))
        
        return violations
    
    def _verify_artifact_referenced(
        self,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[VerificationViolation]:
        """Verify artifact references in rationale exist."""
        violations = []
        rationale = (execution.get('decision', {}) or {}).get('rationale', '') or ''

        claimed_ids = set(re.findall(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}', rationale))
        artifact_ids = {a.get('id') for a in artifacts if a.get('id')}

        if claimed_ids and not artifact_ids:
            violations.append(VerificationViolation(
                rule='artifact_referenced',
                field='artifacts',
                reason='Rationale references artifacts but none were provided'
            ))
        else:
            for claimed in claimed_ids:
                if claimed not in artifact_ids:
                    violations.append(VerificationViolation(
                        rule='artifact_referenced',
                        field='artifacts',
                        reason=f'Referenced artifact {claimed} not found in submission',
                        evidence={'claimed': claimed}
                    ))
        return violations

    def _verify_observation_specificity(
        self,
        artifacts: List[Dict[str, Any]],
        execution: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[VerificationViolation]:
        """Detect vague observation language."""
        violations = []
        rationale = (execution.get('decision', {}) or {}).get('rationale', '') or ''
        rationale_lower = rationale.lower()
        vague_phrases = config.get('vague_phrases', [
            'looks fine', 'seems fine', 'probably', 'maybe', 'appears to be',
            'not sure', "can't tell", 'unclear'
        ])
        min_words = config.get('min_words', 10)

        if len(rationale.split()) < min_words:
            violations.append(VerificationViolation(
                rule='observation_specificity',
                field='rationale',
                reason=f'Rationale too short ({len(rationale.split())} words, expected at least {min_words})'
            ))

        for phrase in vague_phrases:
            if phrase in rationale_lower:
                violations.append(VerificationViolation(
                    rule='observation_specificity',
                    field='rationale',
                    reason=f'Vague language detected: "{phrase}"'
                ))

        return violations


# Convenience function
def verify_execution(
    execution_id: str,
    artifacts: List[Dict[str, Any]],
    execution: Dict[str, Any],
    verifier_names: List[str],
    rule_configs: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Run all verifiers for an execution.
    
    Returns summary of results.
    """
    engine = VerifierEngine()
    rule_configs = rule_configs or {}
    
    results = []
    all_passed = True
    
    for verifier_name in verifier_names:
        config = rule_configs.get(verifier_name, {})
        passed, violations = engine.verify(
            verifier_name,
            artifacts,
            execution,
            config
        )
        
        if not passed:
            all_passed = False
        
        results.append({
            'verifier': verifier_name,
            'passed': passed,
            'violations': [v.to_dict() for v in violations]
        })
    
    return {
        'execution_id': execution_id,
        'all_passed': all_passed,
        'results': results
    }
