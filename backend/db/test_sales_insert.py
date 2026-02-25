import asyncio
import os
import sys

# Add backend to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.db.supabase_client import supabase_service

async def test_sales_insert():
    print("Testing sales_comparables insertion...")
    account_number = "TEST_ACCOUNT_123"
    protest_id = "123e4567-e89b-12d3-a456-426614174000"
    
    # Mock RentCast sales comparable data, using the correct keys
    mock_comps = [
        {
            "address": "123 Test Street",
            "sale_price": 500000,
            "sale_date": "2023-05-15",
            "sqft": 2500,
            "price_per_sqft": 200.0,
            "year_built": 2005,
            "source": "RentCast",
            "distance": 0.5,           # This was the mismatched key
            "similarity": 0.95,        # This was the mismatched key
            "property_type": "Single Family"
        },
        {
            "address": "456 Mock Ave",
            "sale_price": 480000,
            "sale_date": "2023-08-20",
            "sqft": 2400,
            "price_per_sqft": 200.0,
            "year_built": 2004,
            "source": "RentCast",
            "distance": 1.2,
            "similarity": 0.88,
            "property_type": "Single Family"
        }
    ]
    
    # Call the updated function
    await supabase_service.save_sales_comparables(account_number, protest_id, mock_comps)
    
    # Verify the insertion
    print("\nVerifying insertion in database...")
    result = supabase_service.client.table("sales_comparables").select("*").eq("account_number", account_number).execute()
    
    if result.data:
        print(f"✅ Success! Found {len(result.data)} rows in sales_comparables.")
        for row in result.data:
            print(f"  - {row['address']}: ${row['sale_price']} (Similarity: {row['similarity_score']})")
    else:
        print("❌ Failed. Table is still empty for this account.")
        
    # Clean up
    supabase_service.client.table("sales_comparables").delete().eq("account_number", account_number).execute()
    print("Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(test_sales_insert())
