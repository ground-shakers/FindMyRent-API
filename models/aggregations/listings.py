from models.listings import Listing
from beanie import View
from pydantic import Field
from typing import Optional, Annotated

class ListingAnalyticsView(View):
    """Analytics view for aggregating listing data.
    """
    
    total_listings: Annotated[int, Field(serialization_alias="totalListings")]
    
    # Status Stats
    verified_listings: Annotated[int, Field(serialization_alias="verifiedListings")]
    unverified_listings: Annotated[int, Field(serialization_alias="unverifiedListings")]
    rejected_listings: Annotated[int, Field(serialization_alias="rejectedListings")]
    available_listings: Annotated[int, Field(serialization_alias="availableListings")]
    
    # Pricing Stats
    average_price: Annotated[float, Field(serialization_alias="averagePrice")]
    min_price: Annotated[float, Field(serialization_alias="minPrice")]
    max_price: Annotated[float, Field(serialization_alias="maxPrice")]
    
    # Property Types
    single_listings: Annotated[int, Field(serialization_alias="singleListings")]
    shared_listings: Annotated[int, Field(serialization_alias="sharedListings")]
    studio_listings: Annotated[int, Field(serialization_alias="studioListings")]
    flat_listings: Annotated[int, Field(serialization_alias="flatListings")]
    room_listings: Annotated[int, Field(serialization_alias="roomListings")]
    
    # Growth Stats
    listings_today: Annotated[int, Field(serialization_alias="listingsToday")]
    listings_this_month: Annotated[int, Field(serialization_alias="listingsThisMonth")]

    class Settings:
        source = Listing
        pipeline = [
            {
                "$facet": {
                    "stats": [
                        {
                            "$group": {
                                "_id": None,
                                "totalListings": {"$sum": 1},
                                
                                # Status
                                "verifiedListings": {
                                    "$sum": {"$cond": [{"$eq": ["$verified", True]}, 1, 0]}
                                },
                                "unverifiedListings": {
                                    "$sum": {"$cond": [{"$eq": ["$verified", None]}, 1, 0]}
                                },
                                "rejectedListings": {
                                    "$sum": {"$cond": [{"$eq": ["$verified", False]}, 1, 0]}
                                },
                                "availableListings": {
                                    "$sum": {"$cond": [{"$eq": ["$available", True]}, 1, 0]}
                                },
                                
                                # Pricing
                                "averagePrice": {"$avg": "$price"},
                                "minPrice": {"$min": "$price"},
                                "maxPrice": {"$max": "$price"},
                                
                                # Property Type Breakdown
                                "singleListings": {
                                    "$sum": {"$cond": [{"$eq": ["$property_type", "single"]}, 1, 0]}
                                },
                                "sharedListings": {
                                    "$sum": {"$cond": [{"$eq": ["$property_type", "shared"]}, 1, 0]}
                                },
                                "studioListings": {
                                    "$sum": {"$cond": [{"$eq": ["$property_type", "studio"]}, 1, 0]}
                                },
                                "flatListings": {
                                    "$sum": {"$cond": [{"$eq": ["$property_type", "flat"]}, 1, 0]}
                                },
                                "roomListings": {
                                    "$sum": {"$cond": [{"$eq": ["$property_type", "room"]}, 1, 0]}
                                },
                            }
                        }
                    ],
                    "growth": [
                        {
                            "$group": {
                                "_id": None,
                                "listingsToday": {
                                    "$sum": {
                                        "$cond": [
                                            {"$eq": [
                                                {"$dateTrunc": {"date": "$created_at", "unit": "day"}},
                                                {"$dateTrunc": {"date": "$$NOW", "unit": "day"}}
                                            ]},
                                            1,
                                            0
                                        ]
                                    }
                                },
                                "listingsThisMonth": {
                                    "$sum": {
                                        "$cond": [
                                            {"$eq": [
                                                {"$dateTrunc": {"date": "$created_at", "unit": "month"}},
                                                {"$dateTrunc": {"date": "$$NOW", "unit": "month"}}
                                            ]},
                                            1,
                                            0
                                        ]
                                    }
                                }
                            }
                        }
                    ]
                }
            },
            {
                "$project": {
                    "total_listings": {"$arrayElemAt": ["$stats.totalListings", 0]},
                    "verified_listings": {"$arrayElemAt": ["$stats.verifiedListings", 0]},
                    "unverified_listings": {"$arrayElemAt": ["$stats.unverifiedListings", 0]},
                    "rejected_listings": {"$arrayElemAt": ["$stats.rejectedListings", 0]},
                    "available_listings": {"$arrayElemAt": ["$stats.availableListings", 0]},
                    
                    "average_price": {"$ifNull": [{"$arrayElemAt": ["$stats.averagePrice", 0]}, 0]},
                    "min_price": {"$ifNull": [{"$arrayElemAt": ["$stats.minPrice", 0]}, 0]},
                    "max_price": {"$ifNull": [{"$arrayElemAt": ["$stats.maxPrice", 0]}, 0]},
                    
                    "single_listings": {"$arrayElemAt": ["$stats.singleListings", 0]},
                    "shared_listings": {"$arrayElemAt": ["$stats.sharedListings", 0]},
                    "studio_listings": {"$arrayElemAt": ["$stats.studioListings", 0]},
                    "flat_listings": {"$arrayElemAt": ["$stats.flatListings", 0]},
                    "room_listings": {"$arrayElemAt": ["$stats.roomListings", 0]},
                    
                    "listings_today": {"$arrayElemAt": ["$growth.listingsToday", 0]},
                    "listings_this_month": {"$arrayElemAt": ["$growth.listingsThisMonth", 0]},
                }
            }
        ]
