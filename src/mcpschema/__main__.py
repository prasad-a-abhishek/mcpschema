"""Allow ``python -m mcpschema`` to invoke the CLI."""

from mcpschema.cli import main

raise SystemExit(main())