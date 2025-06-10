import hashlib
from datetime import datetime


class AgentBadgeGenerator:
    def __init__(self, agent_record, verification_result, options=None):
        self.agent = agent_record or {}
        self.verification = verification_result or {}
        self.options = {
            "base_url": "https://agentproof.dev",
            "style": "default"
        }
        if options:
            self.options.update(options)

    def generate_badge(self):
        try:
            badge_data = self.prepare_badge_data()
            return {
                "svg": self.create_badge_svg(badge_data),
                "metadata": badge_data,
                "verificationUrl": self.generate_verification_url(badge_data),
                "markdown": self.generate_markdown(badge_data),
                "html": self.generate_html(badge_data)
            }
        except Exception as e:
            print("Badge generation failed:", e)
            return self.create_fallback_badge()

    def prepare_badge_data(self):
        trust_score = self.agent.get("trustScore", 0)
        trust_level = self.get_trust_level(trust_score)
        color = self.get_trust_color(trust_score)
        return {
            "agentId": self.agent.get("id", "unknown"),
            "trustScore": round(trust_score, 2),
            "trustLevel": trust_level,
            "color": color,
            "repositories": len(self.agent.get("repositories", [])),
            "verificationCount": self.agent.get("metadata", {}).get("verificationCount", 0),
            "consistent": self.verification.get("consistent", False),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "hash": self.create_badge_hash()
        }

    def create_badge_svg(self, data):
        width = self.calculate_badge_width(data)
        label_width = 50
        value_width = width - label_width
        return f"""<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='20' role='img' aria-label='agent: {data['trustLevel']}'>
  <title>agent: {data['trustLevel']}</title>
  <linearGradient id='s' x2='0' y2='100%'>
    <stop offset='0' stop-color='#bbb' stop-opacity='.1'/>
    <stop offset='1' stop-opacity='.1'/>
  </linearGradient>
  <clipPath id='r'>
    <rect width='{width}' height='20' rx='3' fill='#fff'/>
  </clipPath>
  <g clip-path='url(#r)'>
    <rect width='{label_width}' height='20' fill='#555'/>
    <rect x='{label_width}' width='{value_width}' height='20' fill='{data['color']}'/>
    <rect width='{width}' height='20' fill='url(#s)'/>
  </g>
  <g fill='#fff' text-anchor='middle' font-family='Verdana,Geneva,DejaVu Sans,sans-serif' text-rendering='geometricPrecision' font-size='110'>
    <text aria-hidden='true' x='{label_width * 5}' y='150' fill='#010101' fill-opacity='.3' transform='scale(.1)' textLength='{(label_width - 10) * 10}'>agent</text>
    <text x='{label_width * 5}' y='140' transform='scale(.1)' fill='#fff' textLength='{(label_width - 10) * 10}'>agent</text>
    <text aria-hidden='true' x='{(label_width + value_width / 2) * 10}' y='150' fill='#010101' fill-opacity='.3' transform='scale(.1)' textLength='{(value_width - 10) * 10}'>{data['trustLevel']}</text>
    <text x='{(label_width + value_width / 2) * 10}' y='140' transform='scale(.1)' fill='#fff' textLength='{(value_width - 10) * 10}'>{data['trustLevel']}</text>
  </g>
</svg>"""

    def calculate_badge_width(self, data):
        return 50 + max(60, len(data["trustLevel"]) * 7 + 20)

    def get_trust_level(self, score):
        if score >= 0.9:
            return "verified"
        elif score >= 0.75:
            return "trusted"
        elif score >= 0.6:
            return "validated"
        elif score >= 0.4:
            return "basic"
        return "unverified"

    def get_trust_color(self, score):
        if score >= 0.9:
            return "#4c1"
        elif score >= 0.75:
            return "#97CA00"
        elif score >= 0.6:
            return "#dfb317"
        elif score >= 0.4:
            return "#fe7d37"
        return "#e05d44"

    def create_badge_hash(self):
        data = {
            "agentId": self.agent.get("id"),
            "trustScore": self.agent.get("trustScore"),
            "timestamp": datetime.utcnow().isoformat().split("T")[0]
        }
        return hashlib.sha256(str(data).encode()).hexdigest()[:16]

    def generate_verification_url(self, data):
        return f"{self.options['base_url']}/verify/{data['hash']}"

    def generate_markdown(self, data):
        return f"[![Agent Verification]({self.options['base_url']}/badge/{data['hash']}.svg)]({data['verificationUrl']})"

    def generate_html(self, data):
        return f'<a href="{data["verificationUrl"]}"><img src="{self.options["base_url"]}/badge/{data["hash"]}.svg" alt="Agent Verification: {data["trustLevel"]}"></a>'

    def create_fallback_badge(self):
        return {
            "svg": self.create_fallback_svg(),
            "metadata": {"error": True, "timestamp": datetime.utcnow().isoformat() + "Z"},
            "verificationUrl": f"{self.options['base_url']}/error",
            "markdown": f'![Agent Verification Error]({self.options["base_url"]}/badge/error.svg)',
            "html": f'<img src="{self.options["base_url"]}/badge/error.svg" alt="Agent Verification Error">'
        }

    def create_fallback_svg(self):
        return """<svg xmlns='http://www.w3.org/2000/svg' width='120' height='20'>
  <rect width='120' height='20' fill='#e05d44'/>
  <text x='60' y='14' fill='white' text-anchor='middle' font-family='Verdana' font-size='11'>verification error</text>
</svg>"""
