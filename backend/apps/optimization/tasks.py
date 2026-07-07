from celery import Task, shared_task
from celery.exceptions import SoftTimeLimitExceeded


class OptimizationTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        from apps.optimization.models import OptimizationJob

        job_id = args[0] if args else kwargs.get("job_id")
        job = OptimizationJob.objects.filter(id=job_id).first()
        if job and job.status not in (
            OptimizationJob.Status.COMPLETED,
            OptimizationJob.Status.FAILED,
        ):
            job.set_error(str(exc))


@shared_task(bind=True, base=OptimizationTask, max_retries=1)
def run_optimization(self, job_id):
    from apps.optimization.models import OptimizationJob
    from apps.optimization.pipeline import OptimizationPipeline
    from django.db import IntegrityError

    job = OptimizationJob.objects.get(id=job_id)

    if job.status == OptimizationJob.Status.COMPLETED:
        return job.metrics

    try:
        job.set_status("running")
        strategy = (
            None if job.strategy == OptimizationJob.Strategy.COMPARE else job.strategy
        )
        metrics = OptimizationPipeline(job).run(strategy=strategy)
        job.set_completed(metrics)
        return metrics
    except IntegrityError:
        job.refresh_from_db()
        return job.metrics
    except SoftTimeLimitExceeded as exc:
        job.set_error(str(exc))
        raise
    except Exception as exc:
        job.set_error(str(exc))
        raise self.retry(exc=exc, countdown=5) from exc
