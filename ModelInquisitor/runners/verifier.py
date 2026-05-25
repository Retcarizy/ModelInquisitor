from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ModelInquisitor.core.models import Claim
from ModelInquisitor.extractors import extract_claims
from ModelInquisitor.generators.mcf import MCFGenerator
from ModelInquisitor.parsers.bpmn import BPMNParser
from ModelInquisitor.strategies.base import TranslatorNamingStrategy
from ModelInquisitor.strategies.third_party_bpmn2mcrl2 import ThirdPartyBpmn2Mcrl2Strategy


@dataclass(frozen=True)
class VerificationResult:
    claim: Claim
    formula: str
    status: str
    truth: bool | None = None
    output: str = ""
    mcf_path: Path | None = None
    pbes_path: Path | None = None
    command: tuple[str, ...] = ()


class VerificationRunner:
    def __init__(self, strategy: TranslatorNamingStrategy | None = None) -> None:
        self.strategy = strategy or ThirdPartyBpmn2Mcrl2Strategy()

    def build_formulas(self, bpmn_path: str | Path) -> list[VerificationResult]:
        model = BPMNParser().parse(bpmn_path)
        self.strategy.prepare(model)
        generator = MCFGenerator(self.strategy)
        return [
            VerificationResult(
                claim=claim,
                formula=generator.generate(claim, model),
                status="generated",
            )
            for claim in extract_claims(model)
        ]

    def verify(
        self,
        bpmn_path: str | Path,
        mcrl2_path: str | Path,
        *,
        work_dir: str | Path | None = None,
        keep_artifacts: bool = False,
    ) -> list[VerificationResult]:
        results = self.build_formulas(bpmn_path)
        if not self._has_mcrl2_toolchain():
            return [
                VerificationResult(
                    claim=result.claim,
                    formula=result.formula,
                    status="not_run",
                    output="mCRL2 command-line tools were not found on PATH.",
                )
                for result in results
            ]

        if work_dir:
            artifact_dir = Path(work_dir)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            return self._verify_in_dir(results, Path(mcrl2_path), artifact_dir)

        artifact_dir = Path(".verify-artifacts")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return self._verify_in_dir(results, Path(mcrl2_path), artifact_dir)

    def _has_mcrl2_toolchain(self) -> bool:
        return all(shutil.which(command) for command in ("mcrl22lps", "lps2pbes", "pbes2bool"))

    def _verify_in_dir(
        self,
        formula_results: list[VerificationResult],
        mcrl2_path: Path,
        artifact_dir: Path,
    ) -> list[VerificationResult]:
        lps_path = artifact_dir / "model.lps"
        model_cmd = ("mcrl22lps", str(mcrl2_path), str(lps_path))
        model_proc = self._run(model_cmd)
        if model_proc.returncode != 0:
            output = self._proc_output(model_proc)
            return [
                VerificationResult(
                    claim=result.claim,
                    formula=result.formula,
                    status="model_error",
                    truth=None,
                    output=output,
                    command=model_cmd,
                )
                for result in formula_results
            ]

        verified: list[VerificationResult] = []
        for index, result in enumerate(formula_results, 1):
            stem = f"claim_{index:03d}_{self._artifact_safe_claim_kind(result.claim.kind.value)}"
            mcf_path = artifact_dir / f"{stem}.mcf"
            pbes_path = artifact_dir / f"{stem}.pbes"
            mcf_path.write_text(result.formula, encoding="utf-8")

            pbes_cmd = ("lps2pbes", "-f", str(mcf_path), str(lps_path), str(pbes_path))
            pbes_proc = self._run(pbes_cmd)
            if pbes_proc.returncode != 0:
                verified.append(
                    VerificationResult(
                        claim=result.claim,
                        formula=result.formula,
                        status="formula_error",
                        truth=None,
                        output=self._proc_output(pbes_proc),
                        mcf_path=mcf_path,
                        pbes_path=pbes_path,
                        command=pbes_cmd,
                    )
                )
                continue

            bool_cmd = ("pbes2bool", str(pbes_path))
            bool_proc = self._run(bool_cmd)
            bool_output = self._proc_output(bool_proc)
            if bool_proc.returncode != 0:
                verified.append(
                    VerificationResult(
                        claim=result.claim,
                        formula=result.formula,
                        status="solver_error",
                        truth=None,
                        output=bool_output,
                        mcf_path=mcf_path,
                        pbes_path=pbes_path,
                        command=bool_cmd,
                    )
                )
                continue

            truth = self._parse_bool_output(bool_output)
            verified.append(
                VerificationResult(
                    claim=result.claim,
                    formula=result.formula,
                    status="passed" if truth else "failed",
                    truth=truth,
                    output=bool_output,
                    mcf_path=mcf_path,
                    pbes_path=pbes_path,
                    command=bool_cmd,
                )
            )
        return verified

    def _run(self, command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, check=False, capture_output=True, text=True)

    def _proc_output(self, proc: subprocess.CompletedProcess[str]) -> str:
        return (proc.stdout or "") + (proc.stderr or "")

    def _parse_bool_output(self, output: str) -> bool:
        for line in reversed(output.splitlines()):
            value = line.strip().lower()
            if value == "true":
                return True
            if value == "false":
                return False
        return False

    def _artifact_safe_claim_kind(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "claim"
