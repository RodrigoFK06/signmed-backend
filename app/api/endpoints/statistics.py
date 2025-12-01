from fastapi import APIRouter, HTTPException
from app.db.mongodb import collection
from app.models.schema import GlobalResultDistributionItem, GlobalResultsDistributionResponse
from typing import List
import logging

# TODO: INDEXING - Consider an index on (evaluation) if the collection is very large, to optimize the /stats/global_distribution aggregation.
# TODO: TESTS - Add unit tests for the global distribution aggregation logic (mocking MongoDB responses and testing percentage calculations).
logger = logging.getLogger(__name__)
router = APIRouter(tags=["Statistics"])

@router.get("/stats/global_distribution",
            response_model=GlobalResultsDistributionResponse,
            summary="Get global distribution of prediction results",
            description="Provides a distribution of all prediction evaluations (e.g., CORRECTO, DUDOSO, INCORRECTO) across the entire system."
            )
async def get_global_distribution():
    try:
        # Assuming 'evaluation' field is always present on relevant records.
        # If not, a $match stage would be: {"$match": {"evaluation": {"$exists": True, "$ne": None}}}
        pipeline = [
            {"$match": {"evaluation": {"$exists": True, "$ne": None}}}, # Ensure evaluation field exists and is not null
            {"$group": {"_id": "$evaluation", "count": {"$sum": 1}}},
            {"$project": {"evaluation_type": "$_id", "count": 1, "_id": 0}}
        ]

        # Execute aggregation query
        # The to_list(length=None) might be memory intensive for very large datasets.
        # For extremely large collections, consider processing results via an async iterator.
        aggregated_results = await collection.aggregate(pipeline).to_list(length=None)

        distribution_items: List[GlobalResultDistributionItem] = []
        total_evaluations = sum(item['count'] for item in aggregated_results)

        if total_evaluations == 0:
            logger.info("No evaluation data found in the system.")
            return GlobalResultsDistributionResponse(
                total_evaluations=0,
                distribution=[]
            )

        for item in aggregated_results:
            evaluation_type = item.get("evaluation_type")
            count = item.get("count", 0)

            # Ensure evaluation_type is a string, as $group _id can be various types if data is inconsistent.
            if not isinstance(evaluation_type, str):
                logger.warning(f"Skipping item with non-string evaluation_type: {evaluation_type}")
                # Potentially decrement total_evaluations if this record was counted, or handle as an error category
                # For now, we skip and the percentage calculation will adjust based on the remaining valid items.
                # However, the sum for total_evaluations already includes this, so this might slightly skew percentages
                # if such data exists. A cleaner $match stage is the best prevention.
                continue

            percentage = (count / total_evaluations) * 100 if total_evaluations > 0 else 0
            
            distribution_items.append(
                GlobalResultDistributionItem(
                    evaluation_type=evaluation_type,
                    count=count,
                    percentage=round(percentage, 2) # Round percentage to 2 decimal places
                )
            )
        
        # Sort distribution by count descending for better readability
        distribution_items.sort(key=lambda x: x.count, reverse=True)

        return GlobalResultsDistributionResponse(
            total_evaluations=total_evaluations,
            distribution=distribution_items
        )

    except Exception as e:
        logger.error("Error fetching global results distribution: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred while fetching global results distribution.")
