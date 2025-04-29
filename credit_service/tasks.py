from celery import shared_task
from .models import User
from .utils import calculate_credit_score
import logging

logger = logging.getLogger(__name__)

@shared_task
def update_user_credit_score(user_id):
    logger.info(f"Task received: Update credit score for user_id {user_id}")
    try:
        user = User.objects.get(id=user_id)
        logger.info(f"Calculating score for User: {user.email_id}, Aadhar: {user.aadhar_id}")

        score = calculate_credit_score(user.aadhar_id)

        user.credit_score = score
        user.save(update_fields=['credit_score', 'updated_at']) 

        logger.info(f"Successfully updated credit score for user_id {user_id} to {score}")
        return f"Score updated to {score} for user {user_id}"

    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found for credit score calculation.")
        return f"User {user_id} not found."
    except Exception as e:
        logger.error(f"Error calculating/updating credit score for user_id {user_id}: {e}", exc_info=True)
        return f"Failed to update score for user {user_id}: {e}"