from models.users import User
    
from beanie import View

from pydantic import Field
from typing import Optional, Annotated

class UserAnalyticsView(View):
    """User analytics view for aggregating user data.
    """
    
    total_users: Annotated[int, Field(serialization_alias="totalUsers")]

    verified_kyc_users: Annotated[int, Field(serialization_alias="verifiedKycUsers")]
    unverified_kyc_users: Annotated[int, Field(serialization_alias="unverifiedKycUsers")]
    kyc_completion_rate: Annotated[float, Field(serialization_alias="kycCompletionRate")]    
    landlords_with_properties: Annotated[int, Field(serialization_alias="landlordsWithProperties")]
    landlords_without_properties: Annotated[int, Field(serialization_alias="landlordsWithoutProperties")]

    top_landlord_id: Annotated[Optional[str], Field(serialization_alias="topLandlordId")]

    average_age: Annotated[Optional[float], Field(serialization_alias="averageAge")]

    age_18_25: Annotated[int, Field(serialization_alias="age18to25")]
    age_26_35: Annotated[int, Field(serialization_alias="age26to35")]
    age_36_45: Annotated[int, Field(serialization_alias="age36to45")]
    age_46_60: Annotated[int, Field(serialization_alias="age46to60")]
    age_60_plus: Annotated[int, Field(serialization_alias="age60Plus")]

    users_today: Annotated[int, Field(serialization_alias="usersToday")]
    users_this_month: Annotated[int, Field(serialization_alias="usersThisMonth")]

    male_users: Annotated[int, Field(serialization_alias="maleUsers")]
    female_users: Annotated[int, Field(serialization_alias="femaleUsers")]

    male_landlords: Annotated[int, Field(serialization_alias="maleLandlords")]
    female_landlords: Annotated[int, Field(serialization_alias="femaleLandlords")]

    class Settings:
        source = User
        pipeline = [
            # ----------------- Normalize DOB + listing count -------------------------------
            {
                "$addFields": {
                    "dobDate": {
                        "$dateFromParts": {
                            "year": "$date_of_birth.year",
                            "month": "$date_of_birth.month",
                            "day": "$date_of_birth.day",
                        }
                    },
                    "listingCount": {
                        "$cond": [
                            {"$isArray": "$listings"},
                            {"$size": "$listings"},
                            0
                        ]
                    },
                }
            },

            # ----------------- Compute age ------------------------------
            {
                "$addFields": {
                    "age": {
                        "$dateDiff": {
                            "startDate": "$dobDate",
                            "endDate": "$$NOW",
                            "unit": "year"
                        }
                    }
                }
            },

            # ----------------- Faceted analytics -------------------------------
            {
                "$facet": {
                    "stats": [
                        {
                            "$group": {
                                "_id": None,

                                "totalUsers": {"$sum": 1},

                                "verifiedKycUsers": {
                                    "$sum": {
                                        "$cond": [{"$eq": ["$kyc_verified", True]}, 1, 0]
                                    }
                                },
                                "unverifiedKycUsers": {
                                    "$sum": {
                                        "$cond": [{"$eq": ["$kyc_verified", False]}, 1, 0]
                                    }
                                },

                                "landlordsWithProperties": {
                                    "$sum": {
                                        "$cond": [
                                            {"$and": [
                                                {"$eq": ["$user_type", "landlord"]},
                                                {"$gt": ["$listingCount", 0]}
                                            ]},
                                            1,
                                            0
                                        ]
                                    }
                                },

                                "landlordsWithoutProperties": {
                                    "$sum": {
                                        "$cond": [
                                            {"$and": [
                                                {"$eq": ["$user_type", "landlord"]},
                                                {"$eq": ["$listingCount", 0]}
                                            ]},
                                            1,
                                            0
                                        ]
                                    }
                                },

                                "averageAge": {"$avg": "$age"},

                                # -------------------------
                                # Age brackets
                                # -------------------------
                                "age18to25": {
                                    "$sum": {"$cond": [{"$and": [{"$gte": ["$age", 18]}, {"$lte": ["$age", 25]}]}, 1, 0]}
                                },
                                "age26to35": {
                                    "$sum": {"$cond": [{"$and": [{"$gte": ["$age", 26]}, {"$lte": ["$age", 35]}]}, 1, 0]}
                                },
                                "age36to45": {
                                    "$sum": {"$cond": [{"$and": [{"$gte": ["$age", 36]}, {"$lte": ["$age", 45]}]}, 1, 0]}
                                },
                                "age46to60": {
                                    "$sum": {"$cond": [{"$and": [{"$gte": ["$age", 46]}, {"$lte": ["$age", 60]}]}, 1, 0]}
                                },
                                "age60Plus": {
                                    "$sum": {"$cond": [{"$gt": ["$age", 60]}, 1, 0]}
                                },

                                # ----------------- Gender stats -------------------------
                                "maleUsers": {
                                    "$sum": {"$cond": [{"$eq": ["$gender", "male"]}, 1, 0]}
                                },
                                "femaleUsers": {
                                    "$sum": {"$cond": [{"$eq": ["$gender", "female"]}, 1, 0]}
                                },

                                "maleLandlords": {
                                    "$sum": {"$cond": [{"$and": [{"$eq": ["$gender", "male"]}, {"$eq": ["$user_type", "landlord"]}]} , 1, 0]}
                                },
                                "femaleLandlords": {
                                    "$sum": {"$cond": [{"$and": [{"$eq": ["$gender", "female"]}, {"$eq": ["$user_type", "landlord"]}]} , 1, 0]}
                                },
                            }
                        }
                    ],

                    # ----------------- Growth -------------------------
                    "growth": [
                        {
                            "$group": {
                                "_id": None,
                                "usersToday": {
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
                                "usersThisMonth": {
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
                                },
                            }
                        }
                    ],

                    # ----------------- Top landlord -----------------
                    "topLandlord": [
                        {"$match": {"user_type": "landlord"}},
                        {"$sort": {"listingCount": -1}},
                        {"$limit": 1},
                        {"$project": {"_id": 1}},
                    ],
                }
            },            # ----------------------------- Final projection + KYC rate ------------------
            {
                "$project": {
                    # Map MongoDB fields to snake_case for Pydantic model
                    "total_users": {"$arrayElemAt": ["$stats.totalUsers", 0]},
                    "verified_kyc_users": {"$arrayElemAt": ["$stats.verifiedKycUsers", 0]},
                    "unverified_kyc_users": {"$arrayElemAt": ["$stats.unverifiedKycUsers", 0]},
                    "landlords_with_properties": {"$arrayElemAt": ["$stats.landlordsWithProperties", 0]},
                    "landlords_without_properties": {"$arrayElemAt": ["$stats.landlordsWithoutProperties", 0]},
                    "average_age": {"$arrayElemAt": ["$stats.averageAge", 0]},
                    "age_18_25": {"$arrayElemAt": ["$stats.age18to25", 0]},
                    "age_26_35": {"$arrayElemAt": ["$stats.age26to35", 0]},
                    "age_36_45": {"$arrayElemAt": ["$stats.age36to45", 0]},
                    "age_46_60": {"$arrayElemAt": ["$stats.age46to60", 0]},
                    "age_60_plus": {"$arrayElemAt": ["$stats.age60Plus", 0]},
                    "male_users": {"$arrayElemAt": ["$stats.maleUsers", 0]},
                    "female_users": {"$arrayElemAt": ["$stats.femaleUsers", 0]},
                    "male_landlords": {"$arrayElemAt": ["$stats.maleLandlords", 0]},
                    "female_landlords": {"$arrayElemAt": ["$stats.femaleLandlords", 0]},
                    "users_today": {"$arrayElemAt": ["$growth.usersToday", 0]},
                    "users_this_month": {"$arrayElemAt": ["$growth.usersThisMonth", 0]},
                    "top_landlord_id": {"$toString": {"$arrayElemAt": ["$topLandlord._id", 0]}},
                    "kyc_completion_rate": {
                        "$cond": [
                            {"$gt": [{"$arrayElemAt": ["$stats.landlordsWithProperties", 0]}, 0]},
                            {
                                "$multiply": [
                                    {"$divide": [
                                        {"$arrayElemAt": ["$stats.verifiedKycUsers", 0]},
                                        {"$arrayElemAt": ["$stats.landlordsWithProperties", 0]}
                                    ]},
                                    100
                                ]
                            },
                            0
                        ]
                    },
                }
            }
        ]
