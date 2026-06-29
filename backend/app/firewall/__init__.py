"""ContextFirewall — the trust layer that audits memories before they reach an agent.

Four audit checks gate every candidate memory:
  - staleness / validity   (a fact that has since changed)
  - contradiction          (a fact contradicted by a newer, established one)
  - secret / sensitivity   (leaked credentials)
  - evidence / trust       (unsupported or unproven claims)

Only memories that pass all checks are assembled into the trusted context pack.
"""
