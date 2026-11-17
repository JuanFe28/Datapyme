"""Fuente de investigación ficticia; nunca contiene respuestas de participantes."""

import json
import sqlite3


def research_database(path):
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE companies (id INTEGER, name TEXT, city TEXT, size TEXT);
            CREATE TABLE company_contacts (company_id INTEGER, name TEXT, detail TEXT);
            CREATE TABLE responses (company_id INTEGER, category TEXT, status TEXT, data TEXT);
        """)
        conn.execute(
            "INSERT INTO companies VALUES (1, ?, ?, ?)",
            ("Comercio Sintético QA", "Bucaramanga", "Pequeña"),
        )
        conn.execute(
            "INSERT INTO company_contacts VALUES (1, ?, ?)",
            ("Persona Sintética", "3000000001 qa@example.test"),
        )
        answers = {
            "M05": "Otra actividad comercial",
            "M10": ["Dificultad para analizar ventas"],
            "M12": ["Ventas por periodo"],
            "M17": "Consulta de ventas e indicadores",
        }
        conn.execute(
            "INSERT INTO responses VALUES (1, ?, ?, ?)", ("mercado", "complete", json.dumps(answers))
        )
    return path
