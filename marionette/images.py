"""Image-name adapter — the single source of truth for an instance's Docker image
tag. The worker container and the grader MUST agree on this tag, so both go through
`instance_image_key`. Delegates to swebench's own spec builder to guarantee parity.
"""

from __future__ import annotations


def instance_image_key(instance: dict, *, namespace: str | None, arch: str) -> str:
    """Return the exact instance image tag swebench's grader builds/uses.

    namespace=None builds/uses local images with no registry prefix (required on
    Apple Silicon). arch is "arm64" or "x86_64".
    """
    from swebench.harness.test_spec.test_spec import make_test_spec

    spec = make_test_spec(instance, namespace=namespace, arch=arch)
    return spec.instance_image_key
