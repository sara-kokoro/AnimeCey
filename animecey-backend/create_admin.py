"""Create an admin user from the command line.

Usage:
    python create_admin.py <username> <email> <password>
"""

from __future__ import annotations

import asyncio
import sys

from database import async_session, init_db
from auth import hash_password
from models import User, UserRole


async def main():
    if len(sys.argv) < 4:
        print("Usage: python create_admin.py <username> <email> <password>")
        sys.exit(1)

    username, email, password = sys.argv[1], sys.argv[2], sys.argv[3]

    await init_db()

    async with async_session() as db:
        from sqlalchemy import select

        existing = await db.execute(
            select(User).where((User.username == username) | (User.email == email))
        )
        if existing.scalar_one_or_none():
            print(f"L'utilisateur '{username}' ou l'email '{email}' existe déjà.")
            sys.exit(1)

        admin = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.admin,
        )
        db.add(admin)
        await db.commit()
        print(f"Admin '{username}' créé avec succès !")


if __name__ == "__main__":
    asyncio.run(main())
