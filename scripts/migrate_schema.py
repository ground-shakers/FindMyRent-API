"""
MongoDB Migration Script - Update Documents for New Schema

This script updates existing documents in MongoDB to match the new schema:
- Adds 'premium: false' field to all users who don't have it
- Adds 'favorites: []' field to all landlords who don't have it

Run this script once to migrate existing data.

Usage:
    python scripts/migrate_schema.py
"""

import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateMany

# Load environment variables
load_dotenv()


async def migrate_users():
    """Add new fields to existing user documents."""
    
    # Connect to MongoDB
    connection_string = os.getenv("DATABASE_CONNECTION_STRING")
    database_name = os.getenv("DATABASE_NAME")
    
    if not connection_string or not database_name:
        print("❌ Error: DATABASE_CONNECTION_STRING or DATABASE_NAME not set in environment")
        return False
    
    client = AsyncIOMotorClient(connection_string)
    db = client[database_name]
    
    print(f"📦 Connected to database: {database_name}")
    print("-" * 50)
    
    try:
        # Migration 1: Add 'premium' field to LandLord documents only (not Admin)
        print("\n🔄 Migration 1: Adding 'premium' field to landlords...")
        
        # Update only landlord documents that don't have 'premium' field
        result = await db.User.update_many(
            {
                "user_type": "landlord",
                "premium": {"$exists": False}
            },
            {"$set": {"premium": False}}
        )
        print(f"   ✅ Updated {result.modified_count} landlord documents with 'premium: false'")
        
        # Migration 2: Add 'favorites' field to LandLord documents
        print("\n🔄 Migration 2: Adding 'favorites' field to landlords...")
        
        # Update landlord documents (user_type = 'landlord') that don't have 'favorites' field
        result = await db.User.update_many(
            {
                "user_type": "landlord",
                "favorites": {"$exists": False}
            },
            {"$set": {"favorites": []}}
        )
        print(f"   ✅ Updated {result.modified_count} landlord documents with 'favorites: []'")
        
        print("\n" + "=" * 50)
        print("✨ Migration completed successfully!")
        print("=" * 50)
        
        # Verification: Count documents with new fields
        print("\n📊 Verification:")
        
        users_with_premium = await db.User.count_documents({"premium": {"$exists": True}})
        total_users = await db.User.count_documents({})
        print(f"   Users with 'premium' field: {users_with_premium}/{total_users}")
        
        landlords_with_favorites = await db.User.count_documents({
            "user_type": "landlord",
            "favorites": {"$exists": True}
        })
        total_landlords = await db.User.count_documents({"user_type": "landlord"})
        print(f"   Landlords with 'favorites' field: {landlords_with_favorites}/{total_landlords}")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        client.close()
        print("\n🔌 Database connection closed")


async def rollback_migration():
    """Rollback the migration by removing the new fields."""
    
    connection_string = os.getenv("DATABASE_CONNECTION_STRING")
    database_name = os.getenv("DATABASE_NAME")
    
    if not connection_string or not database_name:
        print("❌ Error: DATABASE_CONNECTION_STRING or DATABASE_NAME not set in environment")
        return False
    
    client = AsyncIOMotorClient(connection_string)
    db = client[database_name]
    
    print(f"⚠️  Rolling back migration on database: {database_name}")
    print("-" * 50)
    
    try:
        # Remove 'premium' field from all users
        print("\n🔄 Removing 'premium' field from users...")
        result = await db.User.update_many(
            {},
            {"$unset": {"premium": ""}}
        )
        print(f"   ✅ Removed 'premium' from {result.modified_count} documents")
        
        # Remove 'favorites' field from landlords
        print("\n🔄 Removing 'favorites' field from landlords...")
        result = await db.User.update_many(
            {"user_type": "landlord"},
            {"$unset": {"favorites": ""}}
        )
        print(f"   ✅ Removed 'favorites' from {result.modified_count} documents")
        
        print("\n✨ Rollback completed!")
        return True
        
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        return False
    finally:
        client.close()


if __name__ == "__main__":
    import sys
    
    print("=" * 50)
    print("🚀 FindMyRent Schema Migration Script")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        print("\n⚠️  Running ROLLBACK mode")
        asyncio.run(rollback_migration())
    else:
        print("\nThis will update your MongoDB documents with new fields:")
        print("  • premium: false (for all users)")
        print("  • favorites: [] (for all landlords)")
        print()
        
        response = input("Continue? (y/n): ").strip().lower()
        if response == 'y':
            asyncio.run(migrate_users())
        else:
            print("Migration cancelled.")
