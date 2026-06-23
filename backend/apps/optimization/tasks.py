from celery import shared_task


@shared_task(bind=True, max_retries=1)
def run_optimization(self, job_id):
    from apps.optimization.models import OptimizationJob
    from apps.optimization.pipeline import OptimizationPipeline

    job = OptimizationJob.objects.get(id=job_id)
    try:
        job.set_status("running")
        metrics = OptimizationPipeline(job).run()
        job.set_completed(metrics)
        return metrics
    except Exception as exc:
        job.set_error(str(exc))
        raise self.retry(exc=exc, countdown=5) from exc
