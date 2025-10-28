#!/usr/bin/env python3
"""
Proof of Concept: Incremental Training with Gemini 2.5 Pro

This script demonstrates incremental training across multiple games:
Game 1 → Base Gemini 2.5 Pro → basketball-model-v1-1games
Game 2 → basketball-model-v1-1games → basketball-model-v1-2games
Game 3 → basketball-model-v1-2games → basketball-model-v1-3games

Tests the complete flow:
1. Model registry tracking
2. Incremental training execution
3. Performance monitoring
4. Model comparison
"""

import os
import sys
import logging
import argparse
import time
from typing import Dict, Any, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from google.cloud import workflows_v1
from google.cloud.workflows import executions_v1
from google.cloud.workflows.executions_v1 import Execution

from app.services.basketball_model_registry import get_model_registry
from app.services.basketball_training_monitor import get_training_monitor
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IncrementalTrainingPOC:
    """Proof of Concept for incremental training."""
    
    def __init__(self, dry_run: bool = False):
        """
        Initialize the POC.
        
        Args:
            dry_run: If True, simulate without actually triggering workflows
        """
        self.dry_run = dry_run
        self.registry = get_model_registry()
        self.monitor = get_training_monitor()
        
        if not dry_run:
            self.workflows_client = workflows_v1.WorkflowsClient()
            self.executions_client = executions_v1.ExecutionsClient()
    
    def run_poc(
        self,
        game_ids: list[str],
        wait_for_completion: bool = True
    ) -> Dict[str, Any]:
        """
        Run the proof of concept with multiple games.
        
        Args:
            game_ids: List of game IDs to train on sequentially
            wait_for_completion: If True, wait for each training to complete
            
        Returns:
            Dict with POC results
        """
        logger.info("🏀 Starting Incremental Training Proof of Concept")
        logger.info("=" * 80)
        logger.info(f"Games to train: {len(game_ids)}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info(f"Project: {settings.GCP_PROJECT_ID}")
        logger.info("=" * 80)
        
        results = {
            "games_trained": [],
            "model_progression": [],
            "performance_improvements": [],
            "total_cost_usd": 0,
            "total_time_minutes": 0,
            "success": True
        }
        
        # Get initial state
        initial_base_model = self.registry.determine_base_model()
        logger.info(f"\n📊 Initial State:")
        logger.info(f"  Base Model: {initial_base_model['model_id']}")
        logger.info(f"  Games Already Trained: {initial_base_model['games_trained']}")
        logger.info(f"  Is Base Model: {initial_base_model['is_base_model']}")
        
        # Train on each game sequentially
        for i, game_id in enumerate(game_ids, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"🎮 Game {i}/{len(game_ids)}: {game_id}")
            logger.info(f"{'='*80}")
            
            try:
                # Get base model for this training
                base_model = self.registry.determine_base_model()
                
                logger.info(f"\n📋 Training Configuration:")
                logger.info(f"  Base Model: {base_model['model_name']}")
                logger.info(f"  Incremental: {not base_model['is_base_model']}")
                logger.info(f"  Previous Games: {base_model['games_trained']}")
                
                # Run training
                start_time = time.time()
                
                if self.dry_run:
                    training_result = self._simulate_training(game_id, base_model)
                else:
                    training_result = self._execute_training(game_id, wait_for_completion)
                
                elapsed_minutes = (time.time() - start_time) / 60
                
                if training_result["success"]:
                    logger.info(f"\n✅ Training completed for {game_id}")
                    logger.info(f"  Time: {elapsed_minutes:.1f} minutes")
                    
                    # Record results
                    game_result = {
                        "game_id": game_id,
                        "base_model": base_model["model_name"],
                        "was_incremental": not base_model["is_base_model"],
                        "time_minutes": elapsed_minutes,
                        "success": True
                    }
                    
                    if not self.dry_run and "tuned_model" in training_result:
                        game_result["tuned_model"] = training_result["tuned_model"]
                    
                    results["games_trained"].append(game_result)
                    results["total_time_minutes"] += elapsed_minutes
                    
                    # Get updated model info
                    new_model = self.registry.get_latest_tuned_model()
                    if new_model:
                        results["model_progression"].append({
                            "game_id": game_id,
                            "model_name": new_model["model_name"],
                            "version": new_model["version"],
                            "games_trained": new_model["games_trained"]
                        })
                    
                    # Compare with previous model if available
                    if i > 1 and len(results["model_progression"]) >= 2:
                        prev_model = results["model_progression"][-2]
                        curr_model = results["model_progression"][-1]
                        
                        comparison = self.monitor.compare_model_versions(
                            prev_model["model_name"],
                            curr_model["model_name"]
                        )
                        
                        if comparison:
                            results["performance_improvements"].append({
                                "from": prev_model["model_name"],
                                "to": curr_model["model_name"],
                                "improvements": len(comparison.get("improvements", {})),
                                "regressions": len(comparison.get("regressions", {})),
                                "summary": comparison.get("summary", "")
                            })
                    
                    logger.info(f"\n📊 Progress: {i}/{len(game_ids)} games completed")
                    
                else:
                    logger.error(f"\n❌ Training failed for {game_id}")
                    results["success"] = False
                    results["games_trained"].append({
                        "game_id": game_id,
                        "success": False,
                        "error": training_result.get("error", "Unknown error")
                    })
                    break
                    
            except Exception as e:
                logger.error(f"\n❌ Error training game {game_id}: {e}")
                results["success"] = False
                results["games_trained"].append({
                    "game_id": game_id,
                    "success": False,
                    "error": str(e)
                })
                break
        
        # Generate summary
        self._print_summary(results)
        
        return results
    
    def _execute_training(
        self,
        game_id: str,
        wait_for_completion: bool
    ) -> Dict[str, Any]:
        """
        Execute the training workflow for a game.
        
        Args:
            game_id: Game ID to train on
            wait_for_completion: Whether to wait for completion
            
        Returns:
            Dict with training result
        """
        try:
            # Create workflow execution
            workflow_name = (
                f"projects/{settings.GCP_PROJECT_ID}/"
                f"locations/{settings.TRAINING_WORKFLOW_LOCATION}/"
                f"workflows/{settings.TRAINING_WORKFLOW_NAME}"
            )
            
            execution_request = {
                "argument": f'{{"game_id": "{game_id}"}}'
            }
            
            logger.info(f"  🚀 Triggering workflow: {settings.TRAINING_WORKFLOW_NAME}")
            
            execution = self.executions_client.create_execution(
                parent=workflow_name,
                execution=execution_request
            )
            
            execution_name = execution.name
            logger.info(f"  📋 Execution started: {execution_name}")
            
            if wait_for_completion:
                return self._wait_for_execution(execution_name)
            else:
                return {
                    "success": True,
                    "execution_name": execution_name,
                    "message": "Execution started (not waiting for completion)"
                }
                
        except Exception as e:
            logger.error(f"  ❌ Failed to execute training: {e}")
            return {"success": False, "error": str(e)}
    
    def _wait_for_execution(
        self,
        execution_name: str,
        timeout_minutes: int = 120
    ) -> Dict[str, Any]:
        """
        Wait for workflow execution to complete.
        
        Args:
            execution_name: Full execution resource name
            timeout_minutes: Maximum time to wait
            
        Returns:
            Dict with execution result
        """
        logger.info(f"  ⏳ Waiting for execution to complete (timeout: {timeout_minutes}m)")
        
        start_time = time.time()
        poll_interval = 30  # seconds
        
        while True:
            elapsed_minutes = (time.time() - start_time) / 60
            
            if elapsed_minutes > timeout_minutes:
                logger.error(f"  ⏰ Timeout after {timeout_minutes} minutes")
                return {"success": False, "error": "Timeout"}
            
            try:
                execution = self.executions_client.get_execution(name=execution_name)
                state = execution.state
                
                if state == Execution.State.SUCCEEDED:
                    logger.info(f"  ✅ Execution completed successfully")
                    
                    # Parse result
                    result = execution.result
                    return {
                        "success": True,
                        "execution_name": execution_name,
                        "result": result,
                        "tuned_model": self._extract_tuned_model(result)
                    }
                    
                elif state == Execution.State.FAILED:
                    logger.error(f"  ❌ Execution failed")
                    return {
                        "success": False,
                        "execution_name": execution_name,
                        "error": execution.error.message if execution.error else "Unknown error"
                    }
                    
                elif state == Execution.State.CANCELLED:
                    logger.error(f"  ⚠️ Execution was cancelled")
                    return {
                        "success": False,
                        "execution_name": execution_name,
                        "error": "Execution cancelled"
                    }
                
                # Still running
                logger.info(f"  🔄 Execution running... ({elapsed_minutes:.1f}m elapsed)")
                time.sleep(poll_interval)
                
            except Exception as e:
                logger.error(f"  ❌ Error checking execution: {e}")
                return {"success": False, "error": str(e)}
    
    def _simulate_training(
        self,
        game_id: str,
        base_model: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulate training for dry run mode.
        
        Args:
            game_id: Game ID
            base_model: Base model info
            
        Returns:
            Dict with simulated result
        """
        logger.info(f"  🎭 [DRY RUN] Simulating training...")
        
        # Simulate training time
        time.sleep(2)
        
        new_game_count = base_model["games_trained"] + 1
        version = (new_game_count - 1) // 5 + 1
        
        simulated_model = {
            "model_name": f"basketball-model-v{version}-{new_game_count}games",
            "version": version,
            "games_trained": new_game_count
        }
        
        logger.info(f"  ✅ [DRY RUN] Would create: {simulated_model['model_name']}")
        
        return {"success": True, "simulated_model": simulated_model}
    
    def _extract_tuned_model(self, result: str) -> Optional[str]:
        """
        Extract tuned model name from execution result.
        
        Args:
            result: Execution result string
            
        Returns:
            Tuned model name or None
        """
        try:
            import json
            result_dict = json.loads(result)
            return result_dict.get("tuned_model")
        except:
            return None
    
    def _print_summary(self, results: Dict[str, Any]):
        """
        Print a summary of the POC results.
        
        Args:
            results: POC results dict
        """
        logger.info("\n" + "=" * 80)
        logger.info("🏁 PROOF OF CONCEPT SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"\nOverall Success: {'✅ YES' if results['success'] else '❌ NO'}")
        logger.info(f"Games Trained: {len([g for g in results['games_trained'] if g.get('success', False)])}/{len(results['games_trained'])}")
        logger.info(f"Total Time: {results['total_time_minutes']:.1f} minutes")
        
        if results["model_progression"]:
            logger.info(f"\n📊 Model Progression:")
            for model in results["model_progression"]:
                logger.info(f"  {model['game_id']} → {model['model_name']} (v{model['version']})")
        
        if results["performance_improvements"]:
            logger.info(f"\n📈 Performance Comparisons:")
            for comp in results["performance_improvements"]:
                logger.info(f"  {comp['summary']}")
                logger.info(f"    Improvements: {comp['improvements']}, Regressions: {comp['regressions']}")
        
        logger.info("\n" + "=" * 80)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Proof of Concept: Incremental Training with Gemini 2.5 Pro"
    )
    parser.add_argument(
        'game_ids',
        nargs='+',
        help='Game IDs to train on (e.g., game1 game2 game3)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate without actually running training'
    )
    parser.add_argument(
        '--no-wait',
        action='store_true',
        help='Do not wait for training completion'
    )
    
    args = parser.parse_args()
    
    # Run POC
    poc = IncrementalTrainingPOC(dry_run=args.dry_run)
    results = poc.run_poc(
        game_ids=args.game_ids,
        wait_for_completion=not args.no_wait
    )
    
    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()

