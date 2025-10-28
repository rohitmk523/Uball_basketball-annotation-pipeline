"""
Basketball Training Monitor - Track and analyze incremental training performance.

This module monitors:
- Model performance across versions
- Training metrics and quality
- Incremental learning effectiveness
- Overfitting detection
- Cost tracking
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
from google.cloud import storage
from google.cloud import aiplatform
from google.cloud import monitoring_v3

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelPerformanceMetrics:
    """Performance metrics for a model version."""
    model_version: str
    model_id: str
    games_trained: int
    
    # Training metrics
    training_loss: Optional[float] = None
    validation_loss: Optional[float] = None
    training_time_minutes: Optional[float] = None
    
    # Inference metrics
    avg_inference_time_ms: Optional[float] = None
    avg_annotations_per_video: Optional[float] = None
    
    # Quality metrics
    annotation_accuracy: Optional[float] = None
    player_identification_accuracy: Optional[float] = None
    timestamp_precision_error: Optional[float] = None
    
    # Cost metrics
    training_cost_usd: Optional[float] = None
    inference_cost_per_video: Optional[float] = None
    
    # Timestamps
    trained_at: Optional[str] = None
    evaluated_at: Optional[str] = None


class BasketballTrainingMonitor:
    """
    Monitor and track basketball model training performance.
    
    This class tracks:
    - Performance metrics across model versions
    - Incremental learning effectiveness
    - Training costs and efficiency
    - Model quality degradation/improvement
    """
    
    METADATA_BUCKET = "uball-training-data"
    METRICS_FILE = "metadata/training_metrics.json"
    
    def __init__(self):
        """Initialize the training monitor."""
        self.storage_client = storage.Client(project=settings.GCP_PROJECT_ID)
        self.bucket = self.storage_client.bucket(self.METADATA_BUCKET)
        
        # Initialize monitoring client for Cloud Monitoring
        try:
            self.monitoring_client = monitoring_v3.MetricServiceClient()
            self.project_name = f"projects/{settings.GCP_PROJECT_ID}"
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize Cloud Monitoring: {e}")
            self.monitoring_client = None
        
        logger.info("✓ Basketball Training Monitor initialized")
    
    def track_incremental_performance(
        self,
        model_version: str,
        model_id: str,
        games_trained: int,
        metrics: Dict[str, Any]
    ):
        """
        Track performance of a newly trained model.
        
        Args:
            model_version: Model version string (e.g., "basketball-model-v1-5games")
            model_id: Full Vertex AI model ID
            games_trained: Number of games used for training
            metrics: Dict of performance metrics
        """
        try:
            # Create performance metrics object
            perf_metrics = ModelPerformanceMetrics(
                model_version=model_version,
                model_id=model_id,
                games_trained=games_trained,
                training_loss=metrics.get("training_loss"),
                validation_loss=metrics.get("validation_loss"),
                training_time_minutes=metrics.get("training_time_minutes"),
                training_cost_usd=metrics.get("training_cost_usd"),
                trained_at=datetime.utcnow().isoformat()
            )
            
            # Save metrics
            self._save_metrics(perf_metrics)
            
            # Log to Cloud Monitoring if available
            self._log_to_cloud_monitoring(perf_metrics)
            
            logger.info(
                f"✅ Tracked performance for {model_version}: "
                f"Training Loss: {perf_metrics.training_loss}, "
                f"Validation Loss: {perf_metrics.validation_loss}"
            )
            
        except Exception as e:
            logger.error(f"❌ Error tracking performance: {e}")
            raise
    
    def compare_model_versions(
        self,
        version_a: str,
        version_b: str
    ) -> Dict[str, Any]:
        """
        Compare performance between two model versions.
        
        Args:
            version_a: First model version
            version_b: Second model version
            
        Returns:
            Dict with comparison results
        """
        try:
            all_metrics = self._load_all_metrics()
            
            metrics_a = next((m for m in all_metrics if m["model_version"] == version_a), None)
            metrics_b = next((m for m in all_metrics if m["model_version"] == version_b), None)
            
            if not metrics_a or not metrics_b:
                logger.warning(f"⚠️ Could not find metrics for comparison")
                return {}
            
            comparison = {
                "model_a": version_a,
                "model_b": version_b,
                "improvements": {},
                "regressions": {},
                "summary": ""
            }
            
            # Compare key metrics
            metrics_to_compare = [
                "training_loss",
                "validation_loss",
                "annotation_accuracy",
                "training_time_minutes",
                "training_cost_usd"
            ]
            
            for metric in metrics_to_compare:
                val_a = metrics_a.get(metric)
                val_b = metrics_b.get(metric)
                
                if val_a is not None and val_b is not None:
                    change = ((val_b - val_a) / val_a) * 100
                    
                    # Lower is better for loss, time, and cost
                    if metric in ["training_loss", "validation_loss", "training_time_minutes", "training_cost_usd"]:
                        if change < 0:
                            comparison["improvements"][metric] = {
                                "from": val_a,
                                "to": val_b,
                                "change_percent": abs(change)
                            }
                        elif change > 0:
                            comparison["regressions"][metric] = {
                                "from": val_a,
                                "to": val_b,
                                "change_percent": change
                            }
                    else:
                        # Higher is better for accuracy
                        if change > 0:
                            comparison["improvements"][metric] = {
                                "from": val_a,
                                "to": val_b,
                                "change_percent": change
                            }
                        elif change < 0:
                            comparison["regressions"][metric] = {
                                "from": val_a,
                                "to": val_b,
                                "change_percent": abs(change)
                            }
            
            # Generate summary
            improvements_count = len(comparison["improvements"])
            regressions_count = len(comparison["regressions"])
            
            if improvements_count > regressions_count:
                comparison["summary"] = f"✅ Model improved: {improvements_count} metrics better, {regressions_count} worse"
            elif regressions_count > improvements_count:
                comparison["summary"] = f"⚠️ Model regressed: {regressions_count} metrics worse, {improvements_count} better"
            else:
                comparison["summary"] = f"➡️ Mixed results: {improvements_count} improvements, {regressions_count} regressions"
            
            logger.info(f"📊 Model comparison: {comparison['summary']}")
            
            return comparison
            
        except Exception as e:
            logger.error(f"❌ Error comparing models: {e}")
            return {}
    
    def detect_overfitting(self, model_version: str) -> Dict[str, Any]:
        """
        Detect if a model is overfitting.
        
        Args:
            model_version: Model version to check
            
        Returns:
            Dict with overfitting analysis
        """
        try:
            all_metrics = self._load_all_metrics()
            
            model_metrics = next(
                (m for m in all_metrics if m["model_version"] == model_version),
                None
            )
            
            if not model_metrics:
                return {"overfitting_detected": False, "reason": "No metrics found"}
            
            training_loss = model_metrics.get("training_loss")
            validation_loss = model_metrics.get("validation_loss")
            
            if training_loss is None or validation_loss is None:
                return {"overfitting_detected": False, "reason": "Missing loss metrics"}
            
            # Calculate loss gap
            loss_gap = validation_loss - training_loss
            loss_gap_percent = (loss_gap / training_loss) * 100
            
            # Overfitting thresholds
            OVERFITTING_THRESHOLD_PERCENT = 20  # 20% gap indicates overfitting
            HIGH_OVERFITTING_THRESHOLD = 50  # 50% gap indicates severe overfitting
            
            is_overfitting = loss_gap_percent > OVERFITTING_THRESHOLD_PERCENT
            is_severe = loss_gap_percent > HIGH_OVERFITTING_THRESHOLD
            
            result = {
                "overfitting_detected": is_overfitting,
                "severity": "severe" if is_severe else ("moderate" if is_overfitting else "none"),
                "training_loss": training_loss,
                "validation_loss": validation_loss,
                "loss_gap": loss_gap,
                "loss_gap_percent": loss_gap_percent,
                "recommendations": []
            }
            
            if is_severe:
                result["recommendations"] = [
                    "❌ Severe overfitting detected - consider stopping incremental training",
                    "🔄 Retrain from base Gemini 2.5 Pro with more diverse data",
                    "📊 Add regularization or reduce model complexity",
                    "🎯 Collect more diverse game footage"
                ]
            elif is_overfitting:
                result["recommendations"] = [
                    "⚠️ Moderate overfitting detected",
                    "📉 Reduce learning rate for next training",
                    "🎲 Add more data augmentation",
                    "✂️ Consider reducing number of training epochs"
                ]
            else:
                result["recommendations"] = [
                    "✅ Model is generalizing well",
                    "🚀 Safe to continue incremental training"
                ]
            
            logger.info(
                f"🔍 Overfitting analysis for {model_version}: "
                f"{result['severity']} (gap: {loss_gap_percent:.1f}%)"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error detecting overfitting: {e}")
            return {"overfitting_detected": False, "error": str(e)}
    
    def get_training_trend(self, last_n_models: int = 5) -> Dict[str, Any]:
        """
        Get training performance trend across recent models.
        
        Args:
            last_n_models: Number of recent models to analyze
            
        Returns:
            Dict with trend analysis
        """
        try:
            all_metrics = self._load_all_metrics()
            
            if len(all_metrics) == 0:
                return {"trend": "no_data", "message": "No training metrics available"}
            
            # Get last N models
            recent_metrics = all_metrics[-last_n_models:]
            
            # Extract trends
            training_losses = [m.get("training_loss") for m in recent_metrics if m.get("training_loss")]
            validation_losses = [m.get("validation_loss") for m in recent_metrics if m.get("validation_loss")]
            training_costs = [m.get("training_cost_usd") for m in recent_metrics if m.get("training_cost_usd")]
            
            trend = {
                "models_analyzed": len(recent_metrics),
                "training_loss_trend": self._calculate_trend(training_losses),
                "validation_loss_trend": self._calculate_trend(validation_losses),
                "cost_trend": self._calculate_trend(training_costs),
                "latest_metrics": recent_metrics[-1] if recent_metrics else None,
                "summary": ""
            }
            
            # Generate summary
            loss_improving = trend["training_loss_trend"] == "decreasing"
            val_improving = trend["validation_loss_trend"] == "decreasing"
            cost_increasing = trend["cost_trend"] == "increasing"
            
            if loss_improving and val_improving:
                trend["summary"] = "✅ Training is improving consistently - incremental learning is effective"
            elif loss_improving and not val_improving:
                trend["summary"] = "⚠️ Training loss improving but validation stagnating - watch for overfitting"
            elif not loss_improving:
                trend["summary"] = "❌ Training not improving - consider resetting from base model"
            
            if cost_increasing:
                trend["summary"] += " | 💰 Costs are increasing - consider optimization"
            
            logger.info(f"📈 Training trend: {trend['summary']}")
            
            return trend
            
        except Exception as e:
            logger.error(f"❌ Error calculating trend: {e}")
            return {"trend": "error", "error": str(e)}
    
    def _calculate_trend(self, values: List[float]) -> str:
        """
        Calculate trend direction from a list of values.
        
        Args:
            values: List of numeric values
            
        Returns:
            Trend direction: "increasing", "decreasing", or "stable"
        """
        if len(values) < 2:
            return "insufficient_data"
        
        # Simple linear regression slope
        n = len(values)
        x = list(range(n))
        
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        # Determine trend
        if abs(slope) < 0.01:  # Threshold for "stable"
            return "stable"
        elif slope > 0:
            return "increasing"
        else:
            return "decreasing"
    
    def _save_metrics(self, metrics: ModelPerformanceMetrics):
        """
        Save performance metrics to GCS.
        
        Args:
            metrics: ModelPerformanceMetrics object
        """
        try:
            # Load existing metrics
            all_metrics = self._load_all_metrics()
            
            # Add new metrics
            all_metrics.append(metrics.__dict__)
            
            # Save back to GCS
            blob = self.bucket.blob(self.METRICS_FILE)
            blob.upload_from_string(
                json.dumps(all_metrics, indent=2),
                content_type="application/json"
            )
            
            logger.info("✅ Metrics saved to GCS")
            
        except Exception as e:
            logger.error(f"❌ Error saving metrics: {e}")
            raise
    
    def _load_all_metrics(self) -> List[Dict[str, Any]]:
        """
        Load all performance metrics from GCS.
        
        Returns:
            List of metrics dicts
        """
        try:
            blob = self.bucket.blob(self.METRICS_FILE)
            
            if not blob.exists():
                return []
            
            content = blob.download_as_string()
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"❌ Error loading metrics: {e}")
            return []
    
    def _log_to_cloud_monitoring(self, metrics: ModelPerformanceMetrics):
        """
        Log metrics to Cloud Monitoring for alerting and dashboards.
        
        Args:
            metrics: ModelPerformanceMetrics object
        """
        if not self.monitoring_client:
            return
        
        try:
            # Log key metrics
            if metrics.training_loss is not None:
                self._write_metric("training_loss", metrics.training_loss, metrics.model_version)
            
            if metrics.validation_loss is not None:
                self._write_metric("validation_loss", metrics.validation_loss, metrics.model_version)
            
            if metrics.training_cost_usd is not None:
                self._write_metric("training_cost_usd", metrics.training_cost_usd, metrics.model_version)
            
            logger.info("✅ Metrics logged to Cloud Monitoring")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not log to Cloud Monitoring: {e}")
    
    def _write_metric(self, metric_name: str, value: float, model_version: str):
        """
        Write a single metric to Cloud Monitoring.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            model_version: Model version label
        """
        if not self.monitoring_client:
            return
        
        try:
            series = monitoring_v3.TimeSeries()
            series.metric.type = f"custom.googleapis.com/basketball_training/{metric_name}"
            series.metric.labels["model_version"] = model_version
            
            now = datetime.utcnow()
            seconds = int(now.timestamp())
            nanos = int((now.timestamp() - seconds) * 10**9)
            
            interval = monitoring_v3.TimeInterval(
                {"end_time": {"seconds": seconds, "nanos": nanos}}
            )
            
            point = monitoring_v3.Point(
                {"interval": interval, "value": {"double_value": value}}
            )
            
            series.points = [point]
            series.resource.type = "global"
            
            self.monitoring_client.create_time_series(
                name=self.project_name,
                time_series=[series]
            )
            
        except Exception as e:
            logger.warning(f"⚠️ Could not write metric {metric_name}: {e}")


# Global monitor instance
_monitor_instance: Optional[BasketballTrainingMonitor] = None


def get_training_monitor() -> BasketballTrainingMonitor:
    """
    Get or create the global training monitor instance.
    
    Returns:
        BasketballTrainingMonitor instance
    """
    global _monitor_instance
    
    if _monitor_instance is None:
        _monitor_instance = BasketballTrainingMonitor()
    
    return _monitor_instance

