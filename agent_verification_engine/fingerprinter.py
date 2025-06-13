import hashlib
import json
from datetime import datetime
from pathlib import Path
import random
import string


class AgentFingerprinter:
    def __init__(self, scan_results, options=None):
        self.scan_results = scan_results or {}
        self.options = {
            "include_timestamp": False,
            "hash_algorithm": "sha256",
        }
        if options:
            self.options.update(options)

    def generate_fingerprint(self):
        try:
            behavioral = self.extract_behavioral_patterns()
            structural = self.extract_structural_patterns()

            return {
                "behavioral": self.create_hash(behavioral),
                "structural": self.create_hash(structural),
                "composite": self.create_composite_hash(behavioral, structural),
                "metadata": {
                    "generated": datetime.utcnow().isoformat() + "Z",
                    "version": "1.0",
                    "algorithm": self.options["hash_algorithm"],
                },
            }
        except Exception as e:
            print("Fingerprint generation failed:", e)
            return self.create_fallback_fingerprint()

    def extract_behavioral_patterns(self):
        return self.normalize_patterns({
            "api_patterns": self.analyze_api_patterns(),
            "error_handling": self.analyze_error_handling(),
            "rate_limiting": self.analyze_rate_limiting(),
            "data_flow": self.analyze_data_flow(),
        })

    def extract_structural_patterns(self):
        return self.normalize_patterns({
            "architecture": self.analyze_architecture(),
            "dependencies": self.analyze_dependencies(),
            "configuration": self.analyze_configuration(),
            "file_structure": self.analyze_file_structure(),
        })

    def analyze_api_patterns(self):
        files = self.scan_results.get("files", [])
        api_patterns = {
            "providers": set(),
            "callFrequency": 0,
            "authMethods": set(),
        }

        for file in files:
            content = file.get("content", "").lower()
            for provider in ["openai", "anthropic", "cohere", "huggingface"]:
                if provider in content:
                    api_patterns["providers"].add(provider)

            patterns = ["chat.completions.create", "complete(", "fetch(", "axios.get", "axios.post"]
            api_patterns["callFrequency"] += sum(content.count(p) for p in patterns)

            if "bearer" in content or "authorization:" in content:
                api_patterns["authMethods"].add("bearer")
            if "api_key" in content or "apikey" in content:
                api_patterns["authMethods"].add("api_key")

        return {
            "providers": sorted(api_patterns["providers"]),
            "callFrequency": api_patterns["callFrequency"],
            "authMethods": sorted(api_patterns["authMethods"]),
            "complexity": self.calculate_api_complexity(api_patterns),
        }

    def analyze_error_handling(self):
        files = self.scan_results.get("files", [])
        counts = {"tryBlocks": 0, "catchBlocks": 0, "retryLogic": 0, "timeouts": 0}
        for file in files:
            content = file.get("content", "")
            counts["tryBlocks"] += content.count("try")
            counts["catchBlocks"] += content.count("catch")
            counts["retryLogic"] += content.lower().count("retry")
            counts["timeouts"] += content.lower().count("timeout")
        return counts

    def analyze_rate_limiting(self):
        files = self.scan_results.get("files", [])
        counts = {"sleepCalls": 0, "delays": 0, "queues": 0, "semaphores": 0}
        for file in files:
            content = file.get("content", "")
            counts["sleepCalls"] += content.count("sleep")
            counts["delays"] += content.lower().count("delay")
            counts["queues"] += content.lower().count("queue")
            counts["semaphores"] += content.lower().count("semaphore")
        return counts

    def analyze_data_flow(self):
        files = self.scan_results.get("files", [])
        input_sources = set()
        output_targets = set()
        transformations = validations = 0

        for file in files:
            content = file.get("content", "")
            if "stdin" in content or "input(" in content:
                input_sources.add("user_input")
            if "fetch" in content or "axios" in content:
                input_sources.add("api")
            if "readfile" in content or "fs." in content:
                input_sources.add("file")
            if "console.log" in content or "print(" in content:
                output_targets.add("console")
            if "writefile" in content or "fs.write" in content:
                output_targets.add("file")
            transformations += sum(content.lower().count(k) for k in ["transform", "map", "filter", "reduce"])
            validations += sum(content.lower().count(k) for k in ["validate", "sanitize", "clean"])

        return {
            "inputSources": sorted(input_sources),
            "outputTargets": sorted(output_targets),
            "transformations": transformations,
            "validations": validations,
        }

    def analyze_architecture(self):
        files = self.scan_results.get("files", [])
        return {
            "fileCount": len(files),
            "languages": self.detect_languages(files),
            "frameworks": self.detect_frameworks(files),
            "patterns": self.detect_architectural_patterns(files),
        }

    def analyze_dependencies(self):
        files = self.scan_results.get("files", [])
        deps = set()
        for file in files:
            content = file.get("content", "")
            for line in content.splitlines():
                if "import " in line or "from " in line:
                    tokens = line.split()
                    if "import" in tokens:
                        deps.add(tokens[tokens.index("import") + 1].split(".")[0])
        return sorted(deps)

    def analyze_configuration(self):
        return {"configType": "yaml", "hasConfig": True}

    def analyze_file_structure(self):
        return {"structure": "modular"}

    def detect_languages(self, files):
        ext_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".go": "go", ".java": "java", ".cpp": "cpp", ".c": "c"
        }
        langs = {ext_map.get(Path(file.get("path", "")).suffix.lower()) for file in files}
        return sorted(filter(None, langs))

    def detect_frameworks(self, files):
        frameworks = set()
        patterns = {
            "express": "express",
            "fastapi": "fastapi",
            "flask": "flask",
            "react": "react"
        }
        for file in files:
            content = file.get("content", "")
            for fw, keyword in patterns.items():
                if keyword in content.lower():
                    frameworks.add(fw)
        return sorted(frameworks)

    def detect_architectural_patterns(self, files):
        patterns = set()
        for file in files:
            content = file.get("content", "")
            if "class " in content and "def " in content:
                patterns.add("object_oriented")
            if "async " in content or "await " in content:
                patterns.add("async")
        return sorted(patterns)

    def calculate_api_complexity(self, patterns):
        return round(
            len(patterns["providers"]) * 2 +
            min(patterns["callFrequency"] / 10, 5) +
            len(patterns["authMethods"])
        )

    def normalize_patterns(self, patterns):
        normalized = {}
        for key, value in patterns.items():
            if isinstance(value, set):
                normalized[key] = sorted(list(value))
            elif isinstance(value, list):
                normalized[key] = sorted(value)
            else:
                normalized[key] = value
        return normalized

    def create_hash(self, data):
        hash_input = json.dumps(data, sort_keys=True).encode()
        return hashlib.new(self.options["hash_algorithm"], hash_input).hexdigest()

    def create_composite_hash(self, behavioral, structural):
        data = {
            "behavioral": self.create_hash(behavioral),
            "structural": self.create_hash(structural),
            "timestamp": datetime.utcnow().isoformat() + "Z" if self.options["include_timestamp"] else "static"
        }
        return self.create_hash(data)

    def create_fallback_fingerprint(self):
        fallback = {
            "error": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "basic": ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
        }
        return {
            "behavioral": self.create_hash(fallback),
            "structural": self.create_hash(fallback),
            "composite": self.create_hash(fallback),
            "metadata": {
                "generated": datetime.utcnow().isoformat() + "Z",
                "version": "1.0",
                "error": "Fingerprint generation failed, using fallback"
            }
        }
