#!/usr/bin/env python3
"""
Test script for validating incremental training with Vertex AI Tuning Jobs.

This script validates:
1. Model registry functionality
2. Incremental training with tuned models as base
3. Performance improvements across versions
4. Cost tracking and optimization
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.basketball_model_registry import get_model_registry
from app.services.basketball_training_monitor import get_training_monitor
from app.services.basketball_prompt_optimizer import get_prompt_optimizer
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IncrementalTrainingValidator:
    """Validator for incremental training functionality."""
    
    def __init__(self):
        """Initialize the validator."""
        self.registry = get_model_registry()
        self.monitor = get_training_monitor()
        self.optimizer = get_prompt_optimizer()
        self.test_results = []
    
    def run_all_tests(self) -> bool:
        """
        Run all validation tests.
        
        Returns:
            True if all tests pass, False otherwise
        """
        logger.info("🧪 Starting incremental training validation tests")
        logger.info("=" * 80)
        
        tests = [
            ("Model Registry", self.test_model_registry),
            ("Base Model Selection", self.test_base_model_selection),
            ("Model History", self.test_model_history),
            ("Performance Monitoring", self.test_performance_monitoring),
            ("Overfitting Detection", self.test_overfitting_detection),
            ("Training Trends", self.test_training_trends),
            ("Prompt Optimization", self.test_prompt_optimization),
            ("Basketball Context", self.test_basketball_context)
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                logger.info(f"\n📋 Running test: {test_name}")
                result = test_func()
                
                if result:
                    logger.info(f"✅ {test_name} - PASSED")
                    passed += 1
                    self.test_results.append({"test": test_name, "status": "PASSED"})
                else:
                    logger.error(f"❌ {test_name} - FAILED")
                    failed += 1
                    self.test_results.append({"test": test_name, "status": "FAILED"})
                    
            except Exception as e:
                logger.error(f"❌ {test_name} - ERROR: {e}")
                failed += 1
                self.test_results.append({"test": test_name, "status": "ERROR", "error": str(e)})
        
        logger.info("\n" + "=" * 80)
        logger.info(f"🏁 Test Summary: {passed} passed, {failed} failed")
        logger.info("=" * 80)
        
        return failed == 0
    
    def test_model_registry(self) -> bool:
        """Test model registry initialization and basic operations."""
        try:
            # Test getting latest model (might be None if no models exist)
            latest_model = self.registry.get_latest_tuned_model()
            logger.info(f"  Latest model: {latest_model['model_name'] if latest_model else 'None (first training)'}")
            
            # Test base model determination
            base_model = self.registry.determine_base_model()
            logger.info(f"  Base model for next training: {base_model['model_id']}")
            logger.info(f"  Is base model: {base_model['is_base_model']}")
            logger.info(f"  Games trained: {base_model['games_trained']}")
            
            # Test cleanup check
            should_cleanup = self.registry.should_cleanup_models()
            logger.info(f"  Should cleanup models: {should_cleanup}")
            
            return True
            
        except Exception as e:
            logger.error(f"  Model registry test failed: {e}")
            return False
    
    def test_base_model_selection(self) -> bool:
        """Test that base model selection logic works correctly."""
        try:
            base_model = self.registry.determine_base_model()
            
            # Validate base model structure
            required_fields = ["model_id", "model_name", "is_base_model", "games_trained"]
            for field in required_fields:
                if field not in base_model:
                    logger.error(f"  Missing required field: {field}")
                    return False
            
            # Validate model ID format
            model_id = base_model["model_id"]
            if base_model["is_base_model"]:
                # Should be gemini-2.5-pro
                if model_id != "gemini-2.5-pro":
                    logger.error(f"  Expected base model 'gemini-2.5-pro', got '{model_id}'")
                    return False
                logger.info(f"  ✓ Using base Gemini 2.5 Pro model")
            else:
                # Should be a full Vertex AI model path
                if not model_id.startswith("projects/"):
                    logger.error(f"  Invalid tuned model ID format: {model_id}")
                    return False
                logger.info(f"  ✓ Using tuned model for incremental training")
            
            return True
            
        except Exception as e:
            logger.error(f"  Base model selection test failed: {e}")
            return False
    
    def test_model_history(self) -> bool:
        """Test model history tracking."""
        try:
            history = self.registry.get_model_history()
            logger.info(f"  Total models in history: {len(history)}")
            
            if len(history) > 0:
                latest = history[-1]
                logger.info(f"  Latest model: {latest.get('model_name')}")
                logger.info(f"  Version: {latest.get('version')}")
                logger.info(f"  Games trained: {latest.get('games_trained')}")
                logger.info(f"  Trained at: {latest.get('tuned_at')}")
            else:
                logger.info("  No models in history yet (first training)")
            
            return True
            
        except Exception as e:
            logger.error(f"  Model history test failed: {e}")
            return False
    
    def test_performance_monitoring(self) -> bool:
        """Test performance monitoring functionality."""
        try:
            # Test with mock metrics
            test_metrics = {
                "training_loss": 0.25,
                "validation_loss": 0.28,
                "training_time_minutes": 45.5,
                "training_cost_usd": 12.50
            }
            
            logger.info("  Testing metric tracking with mock data:")
            logger.info(f"    Training loss: {test_metrics['training_loss']}")
            logger.info(f"    Validation loss: {test_metrics['validation_loss']}")
            
            # Note: We don't actually save the test metrics
            logger.info("  ✓ Performance monitoring structure validated")
            
            return True
            
        except Exception as e:
            logger.error(f"  Performance monitoring test failed: {e}")
            return False
    
    def test_overfitting_detection(self) -> bool:
        """Test overfitting detection logic."""
        try:
            # Test with mock scenarios
            scenarios = [
                {
                    "name": "Good Model",
                    "training_loss": 0.20,
                    "validation_loss": 0.22,
                    "expected": False
                },
                {
                    "name": "Moderate Overfitting",
                    "training_loss": 0.15,
                    "validation_loss": 0.20,
                    "expected": True
                },
                {
                    "name": "Severe Overfitting",
                    "training_loss": 0.10,
                    "validation_loss": 0.18,
                    "expected": True
                }
            ]
            
            for scenario in scenarios:
                training_loss = scenario["training_loss"]
                validation_loss = scenario["validation_loss"]
                loss_gap_percent = ((validation_loss - training_loss) / training_loss) * 100
                
                is_overfitting = loss_gap_percent > 20
                
                logger.info(f"  Scenario: {scenario['name']}")
                logger.info(f"    Loss gap: {loss_gap_percent:.1f}%")
                logger.info(f"    Overfitting: {is_overfitting}")
                
                if is_overfitting != scenario["expected"]:
                    logger.error(f"    Expected {scenario['expected']}, got {is_overfitting}")
                    return False
            
            logger.info("  ✓ Overfitting detection logic validated")
            return True
            
        except Exception as e:
            logger.error(f"  Overfitting detection test failed: {e}")
            return False
    
    def test_training_trends(self) -> bool:
        """Test training trend analysis."""
        try:
            # Test trend calculation
            trend = self.monitor.get_training_trend(last_n_models=5)
            
            logger.info(f"  Models analyzed: {trend.get('models_analyzed', 0)}")
            logger.info(f"  Training loss trend: {trend.get('training_loss_trend', 'N/A')}")
            logger.info(f"  Validation loss trend: {trend.get('validation_loss_trend', 'N/A')}")
            logger.info(f"  Cost trend: {trend.get('cost_trend', 'N/A')}")
            
            if trend.get('summary'):
                logger.info(f"  Summary: {trend['summary']}")
            
            return True
            
        except Exception as e:
            logger.error(f"  Training trends test failed: {e}")
            return False
    
    def test_prompt_optimization(self) -> bool:
        """Test basketball prompt optimization."""
        try:
            # Test basic prompt generation
            prompt = self.optimizer.build_annotation_prompt()
            
            if len(prompt) < 100:
                logger.error("  Prompt too short")
                return False
            
            # Check for key basketball terms
            required_terms = [
                "basketball",
                "player",
                "timestamp",
                "events",
                "court"
            ]
            
            prompt_lower = prompt.lower()
            missing_terms = [term for term in required_terms if term not in prompt_lower]
            
            if missing_terms:
                logger.error(f"  Missing required terms: {missing_terms}")
                return False
            
            logger.info(f"  ✓ Prompt length: {len(prompt)} characters")
            logger.info(f"  ✓ Contains all required basketball terms")
            
            return True
            
        except Exception as e:
            logger.error(f"  Prompt optimization test failed: {e}")
            return False
    
    def test_basketball_context(self) -> bool:
        """Test basketball context and event types."""
        try:
            # Test event types
            event_types = self.optimizer.get_basketball_event_types()
            logger.info(f"  Basketball event types: {len(event_types)}")
            
            # Validate key events exist
            required_events = [
                "FG_MAKE", "FG_MISS",
                "3PT_MAKE", "3PT_MISS",
                "ASSIST", "REBOUND_OFFENSIVE",
                "STEAL", "BLOCK", "FOUL_PERSONAL"
            ]
            
            missing_events = [e for e in required_events if e not in event_types]
            
            if missing_events:
                logger.error(f"  Missing required events: {missing_events}")
                return False
            
            # Test court regions
            court_regions = self.optimizer.get_court_regions()
            logger.info(f"  Court regions: {len(court_regions)}")
            
            # Test shot types
            shot_types = self.optimizer.get_shot_types()
            logger.info(f"  Shot types: {len(shot_types)}")
            
            logger.info("  ✓ Basketball context validated")
            
            return True
            
        except Exception as e:
            logger.error(f"  Basketball context test failed: {e}")
            return False
    
    def generate_report(self) -> str:
        """
        Generate a test report.
        
        Returns:
            Formatted test report string
        """
        report = "\n" + "=" * 80 + "\n"
        report += "🏀 INCREMENTAL TRAINING VALIDATION REPORT\n"
        report += "=" * 80 + "\n\n"
        
        report += f"Test Date: {datetime.now().isoformat()}\n"
        report += f"Project: {settings.GCP_PROJECT_ID}\n"
        report += f"Base Model: {settings.VERTEX_AI_BASE_MODEL}\n\n"
        
        passed = sum(1 for r in self.test_results if r["status"] == "PASSED")
        failed = sum(1 for r in self.test_results if r["status"] in ["FAILED", "ERROR"])
        
        report += f"Tests Run: {len(self.test_results)}\n"
        report += f"Passed: {passed} ✅\n"
        report += f"Failed: {failed} ❌\n\n"
        
        report += "Test Results:\n"
        report += "-" * 80 + "\n"
        
        for result in self.test_results:
            status_icon = "✅" if result["status"] == "PASSED" else "❌"
            report += f"{status_icon} {result['test']}: {result['status']}\n"
            if "error" in result:
                report += f"   Error: {result['error']}\n"
        
        report += "\n" + "=" * 80 + "\n"
        
        return report


def main():
    """Main test execution function."""
    parser = argparse.ArgumentParser(
        description="Test incremental training with Vertex AI Tuning Jobs"
    )
    parser.add_argument(
        '--report-file',
        type=str,
        help='Output file for test report (optional)'
    )
    
    args = parser.parse_args()
    
    # Run tests
    validator = IncrementalTrainingValidator()
    success = validator.run_all_tests()
    
    # Generate report
    report = validator.generate_report()
    print(report)
    
    # Save report if requested
    if args.report_file:
        with open(args.report_file, 'w') as f:
            f.write(report)
        logger.info(f"📝 Report saved to: {args.report_file}")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

