"""SQLite access for species / profiles / noise sources.

The DB file lives at <package_data>/lethe.db; schema and
seeds are versioned alongside it as SQL files. First use
auto-initializes the DB; pass reseed=True to rebuild.
"""
import os
import sqlite3


DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
)
DB_PATH = os.path.join(DATA_DIR, "lethe.db")
SCHEMA_PATH = os.path.join(DATA_DIR, "schema.sql")
SEEDS_PATH = os.path.join(DATA_DIR, "seeds.sql")


def _read_sql(path):
    """Read a .sql file as a single string."""
    with open(path) as fp:
        return fp.read()


def init_db(reseed=False):
    """Create DB + apply schema + seed if missing.

    If reseed is True the .db file is removed first so the
    seeds are re-applied from scratch (useful when they
    change).
    """
    if reseed and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    exists = os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not exists:
        conn.executescript(_read_sql(SCHEMA_PATH))
        conn.executescript(_read_sql(SEEDS_PATH))
        conn.commit()
    return conn


def connect():
    """Return a connection; init DB lazily if absent."""
    return init_db(reseed=False)


def _norm(query):
    """Normalize a user-facing name for lookup."""
    return query.lower().replace("_", " ").strip()


def _sql_norm(col):
    """SQL fragment matching _norm on a TEXT column."""
    return f"LOWER(REPLACE({col}, '_', ' '))"


def list_species(conn):
    """Return all species rows as list of dicts."""
    cur = conn.execute(
        "SELECT id, scientific_name, common_name, notes "
        "FROM species ORDER BY common_name"
    )
    return [dict(r) for r in cur.fetchall()]


def get_species(conn, query):
    """Look up a species by common or scientific name."""
    q = _norm(query)
    sql = (
        "SELECT id, scientific_name, common_name, notes "
        "FROM species WHERE "
        f"{_sql_norm('common_name')}=? OR "
        f"{_sql_norm('scientific_name')}=?"
    )
    cur = conn.execute(sql, (q, q))
    row = cur.fetchone()
    if row is None:
        raise KeyError(f"unknown species: {query!r}")
    return dict(row)


def list_profiles(conn, species_id):
    """All profiles for a given species_id."""
    cur = conn.execute(
        "SELECT id, species_id, name, freq_lo, freq_hi, "
        "notes FROM signal_profile "
        "WHERE species_id=? ORDER BY name",
        (species_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def get_profile(conn, species_id, name=None):
    """Return a single profile for species.

    If name is given, that profile is returned or KeyError.
    If name is None, returns the only profile if exactly
    one exists else raises (ambiguous).
    """
    profiles = list_profiles(conn, species_id)
    if not profiles:
        raise KeyError(
            f"no profiles for species_id={species_id}"
        )
    if name is None:
        if len(profiles) == 1:
            return profiles[0]
        names = ", ".join(p["name"] for p in profiles)
        raise KeyError(
            f"species has multiple profiles; use --profile "
            f"to pick one of: {names}"
        )
    q = _norm(name)
    for p in profiles:
        if _norm(p["name"]) == q:
            return p
    names = ", ".join(p["name"] for p in profiles)
    raise KeyError(
        f"unknown profile {name!r}; available: {names}"
    )


def list_noise_sources(conn):
    """Return all noise_source rows as list of dicts."""
    cur = conn.execute(
        "SELECT id, name, category, freq_lo, freq_hi, "
        "temporal_character, notes "
        "FROM noise_source ORDER BY category, name"
    )
    return [dict(r) for r in cur.fetchall()]


def get_noise_sources(conn, names):
    """Return list of noise_source rows for given names.

    Unknown names raise KeyError naming the offenders.
    """
    resolved = []
    missing = []
    sql = (
        "SELECT id, name, category, freq_lo, freq_hi, "
        "temporal_character, notes "
        f"FROM noise_source WHERE {_sql_norm('name')}=?"
    )
    for n in names:
        q = _norm(n)
        cur = conn.execute(sql, (q,))
        row = cur.fetchone()
        if row is None:
            missing.append(n)
        else:
            resolved.append(dict(row))
    if missing:
        raise KeyError(
            "unknown noise source(s): "
            + ", ".join(repr(m) for m in missing)
        )
    return resolved
